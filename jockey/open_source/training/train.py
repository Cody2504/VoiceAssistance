"""
Train the grounding head on Charades-STA precomputed features.

Pipeline (assumes Phases 1 + 3 ran):
    1. Per-video features extracted to features/charades/<vid>.npz
    2. Query embeddings cached in features/charades/query_emb.npz
    3. Train annotations at data/charades_sta_train.txt
    4. Test  annotations at data/charades_sta_test.txt

Usage:
    python -m jockey.open_source.training.train \\
        --features-dir features/charades/ \\
        --train-ann   data/charades_sta_train.txt \\
        --test-ann    data/charades_sta_test.txt \\
        --query-cache features/charades/query_emb.npz \\
        --out-dir     runs/exp1/

Outputs (in --out-dir):
    config.json      — frozen hyperparameters
    train_log.csv    — per-step loss
    val_log.csv      — per-epoch eval metrics
    best.pt          — checkpoint with highest R@1@IoU=0.5
    last.pt          — most recent epoch checkpoint
"""
import argparse
import csv
import hashlib
import json
import logging
import math
import os
import random
import time
from dataclasses import asdict
from typing import Dict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from jockey.open_source.training.charades_sta import (
    CharadesSTADataset,
    grounding_collate,
    parse_annotations,
)
from jockey.open_source.training.grounding_head import (
    GroundingConfig,
    GroundingHead,
    grounding_loss,
    mean_iou,
    recall_at_iou,
)

log = logging.getLogger(__name__)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _video_split_score(video_id: str, seed: int) -> float:
    """Stable [0, 1) score per (video_id, seed). MD5-based so it does NOT depend
    on the size or ordering of the surrounding corpus — critical for incremental
    training rounds where the train corpus grows over time."""
    h = hashlib.md5(f"{video_id}|{seed}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0x100000000  # first 32 bits → [0, 1)


def split_train_val(records, val_ratio: float, seed: int):
    """Split annotation records by VIDEO_ID into (train, val).

    Splitting by video_id (not by query line) prevents leakage: otherwise the
    same video's frames could appear in both train and val with different
    queries, and the model would memorize the visual features per video.

    The split is HASH-STABLE: video VID with score < val_ratio always lands in
    val, regardless of how many other videos are in `records`. This means you
    can extract 1000 more videos and re-train — the val set won't migrate.
    """
    train, val = [], []
    for r in records:
        score = _video_split_score(r["video_id"], seed)
        if score < val_ratio:
            val.append(r)
        else:
            train.append(r)
    return train, val


def cosine_warmup_lr(step: int, total: int, warmup: int, base_lr: float, min_lr: float = 1e-6) -> float:
    if step < warmup:
        return base_lr * (step + 1) / max(1, warmup)
    progress = (step - warmup) / max(1, total - warmup)
    return min_lr + 0.5 * (base_lr - min_lr) * (1 + math.cos(math.pi * progress))


def to_device(batch: Dict, device: str) -> Dict:
    out: Dict = {}
    for k, v in batch.items():
        out[k] = v.to(device, non_blocking=True) if isinstance(v, torch.Tensor) else v
    return out


@torch.no_grad()
def evaluate(model: GroundingHead, loader: DataLoader, device: str, cfg: GroundingConfig) -> Dict[str, float]:
    model.eval()
    all_pred, all_gt = [], []
    for batch in loader:
        batch = to_device(batch, device)
        _, bnd = model(
            visual=batch["visual"],
            query=batch["query"],
            audio=batch["audio"] if cfg.use_audio else None,
            caption=batch["caption"] if cfg.use_caption else None,
            global_emb=batch["global_emb"] if cfg.use_global else None,
            shot_mask=batch["shot_mask"],
        )
        all_pred.append(bnd.cpu())
        all_gt.append(batch["gt_boundary"].cpu())
    if not all_pred:
        # Empty loader — return NaN metrics so callers can detect "no eval data"
        return {
            "R@1@IoU=0.3": float("nan"),
            "R@1@IoU=0.5": float("nan"),
            "R@1@IoU=0.7": float("nan"),
            "mIoU": float("nan"),
        }
    pred = torch.cat(all_pred, dim=0)
    gt = torch.cat(all_gt, dim=0)
    return {
        "R@1@IoU=0.3": recall_at_iou(pred, gt, 0.3),
        "R@1@IoU=0.5": recall_at_iou(pred, gt, 0.5),
        "R@1@IoU=0.7": recall_at_iou(pred, gt, 0.7),
        "mIoU": mean_iou(pred, gt),
    }


def save_checkpoint(path: str, model, optimizer, epoch: int, best_r05: float, cfg: GroundingConfig) -> None:
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "epoch": epoch,
            "best_r05": best_r05,
            "config": asdict(cfg),
        },
        path,
    )


def open_csv_logger(path: str, header: str):
    new_file = not os.path.isfile(path)
    f = open(path, "a", newline="")
    if new_file:
        f.write(header + "\n")
    return f


def train(args: argparse.Namespace) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    set_seed(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "config.json"), "w") as f:
        json.dump(vars(args), f, indent=2)

    # Datasets — train/val/test with VIDEO-LEVEL split for val to avoid leakage.
    all_train_recs = parse_annotations(args.train_ann)
    test_recs = parse_annotations(args.test_ann)
    train_recs, val_recs = split_train_val(all_train_recs, args.val_ratio, args.val_seed)
    log.info(
        f"Split (by video_id, seed={args.val_seed}, val_ratio={args.val_ratio}): "
        f"train={len(train_recs)} val={len(val_recs)} test={len(test_recs)} "
        f"(pre-feature-existence-filter)"
    )
    if not train_recs:
        raise RuntimeError(
            "No training records after train/val split. "
            "Check that --train-ann is valid and not empty."
        )

    ds_kwargs = dict(
        features_dir=args.features_dir,
        query_cache_path=args.query_cache,
        max_shots=args.max_shots,
    )
    train_ds = CharadesSTADataset(annotations=train_recs, **ds_kwargs)
    val_ds   = CharadesSTADataset(annotations=val_recs,   **ds_kwargs)
    test_ds  = CharadesSTADataset(annotations=test_recs,  **ds_kwargs)

    loader_kwargs = dict(
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        collate_fn=grounding_collate,
        pin_memory=(args.device == "cuda"),
    )
    train_loader = DataLoader(train_ds, shuffle=True,  **loader_kwargs)
    val_loader   = DataLoader(val_ds,   shuffle=False, **loader_kwargs)
    test_loader  = DataLoader(test_ds,  shuffle=False, **loader_kwargs)

    # Model
    cfg = GroundingConfig(
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        max_shots=args.max_shots,
        dropout=args.dropout,
        use_audio=not args.no_audio,
        use_caption=not args.no_caption,
        use_global=not args.no_global,
    )
    model = GroundingHead(cfg).to(args.device)
    log.info(
        f"Model: {model.num_trainable_params()/1e6:.2f}M params, "
        f"hidden={cfg.hidden_dim} layers={cfg.num_layers} heads={cfg.num_heads} "
        f"audio={cfg.use_audio} caption={cfg.use_caption} global={cfg.use_global}"
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = args.epochs * len(train_loader)
    warmup_steps = int(total_steps * args.warmup_ratio)

    use_amp = args.mixed_precision and args.device == "cuda"
    # torch.amp.GradScaler is the PyTorch 2.x API; the old torch.cuda.amp.* is deprecated.
    scaler = torch.amp.GradScaler("cuda") if use_amp else None

    # Resume
    start_epoch = 0
    best_r05 = -1.0  # negative sentinel so the first eval always wins and writes best.pt
    if args.resume and os.path.isfile(args.resume):
        ckpt = torch.load(args.resume, map_location=args.device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        start_epoch = ckpt["epoch"] + 1
        best_r05 = ckpt.get("best_r05", 0.0)
        log.info(f"Resumed from {args.resume} at epoch {start_epoch}, best R@0.5={best_r05:.4f}")

    train_log_f = open_csv_logger(
        os.path.join(args.out_dir, "train_log.csv"),
        "epoch,step,loss,rel,l1,iou_loss,mIoU,lr",
    )
    val_log_f = open_csv_logger(
        os.path.join(args.out_dir, "val_log.csv"),
        "epoch,r03,r05,r07,mIoU",
    )

    # Resolve total target epochs. `--add-epochs N` means "train N more from where
    # we resumed", overriding `--epochs`. Lets incremental rounds say "+30 epochs"
    # without having to track cumulative epoch counts manually.
    if args.add_epochs is not None and args.add_epochs > 0:
        target_epochs = start_epoch + args.add_epochs
        log.info(f"--add-epochs {args.add_epochs}: will train epochs {start_epoch}..{target_epochs-1}")
    else:
        target_epochs = args.epochs

    global_step = start_epoch * len(train_loader)

    for epoch in range(start_epoch, target_epochs):
        model.train()
        t_ep = time.time()
        for step, batch in enumerate(train_loader):
            batch = to_device(batch, args.device)

            lr = cosine_warmup_lr(global_step, total_steps, warmup_steps, args.lr)
            for pg in optimizer.param_groups:
                pg["lr"] = lr

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with torch.amp.autocast(device_type="cuda"):
                    rel_logits, bnd = model(
                        visual=batch["visual"],
                        query=batch["query"],
                        audio=batch["audio"] if cfg.use_audio else None,
                        caption=batch["caption"] if cfg.use_caption else None,
                        global_emb=batch["global_emb"] if cfg.use_global else None,
                        shot_mask=batch["shot_mask"],
                    )
                    losses = grounding_loss(
                        rel_logits, bnd,
                        batch["gt_relevance"], batch["gt_boundary"],
                        shot_mask=batch["shot_mask"],
                        w_rel=args.w_rel, w_l1=args.w_l1, w_iou=args.w_iou,
                    )
                scaler.scale(losses["total"]).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
                scaler.step(optimizer)
                scaler.update()
            else:
                rel_logits, bnd = model(
                    visual=batch["visual"],
                    query=batch["query"],
                    audio=batch["audio"] if cfg.use_audio else None,
                    caption=batch["caption"] if cfg.use_caption else None,
                    global_emb=batch["global_emb"] if cfg.use_global else None,
                    shot_mask=batch["shot_mask"],
                )
                losses = grounding_loss(
                    rel_logits, bnd,
                    batch["gt_relevance"], batch["gt_boundary"],
                    shot_mask=batch["shot_mask"],
                    w_rel=args.w_rel, w_l1=args.w_l1, w_iou=args.w_iou,
                )
                losses["total"].backward()
                nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
                optimizer.step()

            if global_step % args.log_every == 0:
                log.info(
                    f"ep {epoch:3d} step {step:5d}/{len(train_loader)}  "
                    f"loss={losses['total'].item():.4f}  "
                    f"rel={losses['rel'].item():.4f}  "
                    f"l1={losses['l1'].item():.4f}  "
                    f"iou_l={losses['iou_loss'].item():.4f}  "
                    f"mIoU={losses['mIoU'].item():.4f}  lr={lr:.2e}"
                )
            train_log_f.write(
                f"{epoch},{global_step},"
                f"{losses['total'].item():.6f},{losses['rel'].item():.6f},"
                f"{losses['l1'].item():.6f},{losses['iou_loss'].item():.6f},"
                f"{losses['mIoU'].item():.6f},{lr:.6e}\n"
            )
            train_log_f.flush()
            global_step += 1

        # Eval on VAL set for early stopping (test is held out till the end).
        if (epoch + 1) % args.eval_every == 0 or epoch == args.epochs - 1:
            metrics = evaluate(model, val_loader, args.device, cfg)
            log.info(
                f"[ep {epoch}] val  "
                f"R@0.3={metrics['R@1@IoU=0.3']:.4f}  "
                f"R@0.5={metrics['R@1@IoU=0.5']:.4f}  "
                f"R@0.7={metrics['R@1@IoU=0.7']:.4f}  "
                f"mIoU={metrics['mIoU']:.4f}"
            )
            val_log_f.write(
                f"{epoch},{metrics['R@1@IoU=0.3']:.6f},"
                f"{metrics['R@1@IoU=0.5']:.6f},"
                f"{metrics['R@1@IoU=0.7']:.6f},{metrics['mIoU']:.6f}\n"
            )
            val_log_f.flush()

            r05 = metrics["R@1@IoU=0.5"]
            if r05 > best_r05:
                best_r05 = r05
                save_checkpoint(
                    os.path.join(args.out_dir, "best.pt"),
                    model, optimizer, epoch, best_r05, cfg,
                )
                log.info(f"  saved best.pt (val R@0.5={best_r05:.4f})")

        # Always save last (checkpoint after each epoch for resume)
        save_checkpoint(
            os.path.join(args.out_dir, "last.pt"),
            model, optimizer, epoch, best_r05, cfg,
        )
        log.info(f"epoch {epoch} done in {time.time()-t_ep:.1f}s")

    train_log_f.close()
    val_log_f.close()
    log.info(f"Training complete. Best val R@1@IoU=0.5 = {best_r05:.4f}")

    # Final test evaluation — load best.pt (or fall back to last.pt) and run on
    # held-out test set ONCE. This number is the one you report in the thesis.
    best_path = os.path.join(args.out_dir, "best.pt")
    last_path = os.path.join(args.out_dir, "last.pt")
    ckpt_path = best_path if os.path.isfile(best_path) else last_path
    if os.path.isfile(ckpt_path):
        log.info(f"Loading {os.path.basename(ckpt_path)} for final test eval...")
        ckpt = torch.load(ckpt_path, map_location=args.device)
        model.load_state_dict(ckpt["model"])
        test_metrics = evaluate(model, test_loader, args.device, cfg)
        log.info(
            f"=== FINAL TEST (held-out, from {os.path.basename(ckpt_path)}) ===  "
            f"R@0.3={test_metrics['R@1@IoU=0.3']:.4f}  "
            f"R@0.5={test_metrics['R@1@IoU=0.5']:.4f}  "
            f"R@0.7={test_metrics['R@1@IoU=0.7']:.4f}  "
            f"mIoU={test_metrics['mIoU']:.4f}"
        )
        with open(os.path.join(args.out_dir, "test_metrics.json"), "w") as f:
            json.dump(test_metrics, f, indent=2)
    else:
        log.warning("No checkpoint found for final test eval.")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train the grounding head on Charades-STA features.")
    # Data
    p.add_argument("--features-dir", required=True, help="Dir with per-video <vid>.npz feature files")
    p.add_argument("--train-ann", required=True, help="Charades-STA train .txt")
    p.add_argument("--test-ann", required=True, help="Charades-STA test .txt")
    p.add_argument("--query-cache", required=True, help="Cached query embeddings .npz")
    p.add_argument("--out-dir", required=True, help="Run output dir (checkpoints + logs)")
    # Architecture
    p.add_argument("--hidden-dim", type=int, default=512)
    p.add_argument("--num-layers", type=int, default=4)
    p.add_argument("--num-heads", type=int, default=8)
    p.add_argument("--max-shots", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--no-audio", action="store_true", help="Ablation: drop audio modality")
    p.add_argument("--no-caption", action="store_true", help="Ablation: drop caption modality")
    p.add_argument("--no-global", action="store_true", help="Ablation: drop [GLOBAL] token")
    # Optimization
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--epochs", type=int, default=30,
                   help="Target final epoch count (absolute, not incremental).")
    p.add_argument("--add-epochs", type=int, default=None,
                   help="Train this many MORE epochs from the resume point. "
                        "Overrides --epochs when set. Useful for incremental rounds.")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--warmup-ratio", type=float, default=0.05)
    p.add_argument("--grad-clip", type=float, default=1.0)
    # Loss weights — defaults follow Moment-DETR/QD-DETR conventions:
    # boundary L1 is weighted 10× larger than the BCE relevance loss so the
    # boundary head receives proportional gradient, escaping the "predict the
    # mean moment" failure mode observed with w_l1=1.0 / w_iou=0.5.
    p.add_argument("--w-rel", type=float, default=1.0)
    p.add_argument("--w-l1", type=float, default=10.0)
    p.add_argument("--w-iou", type=float, default=1.0)
    p.add_argument("--mixed-precision", action="store_true", help="fp16 AMP (CUDA only)")
    # Validation split (carved from train_ann; test_ann stays held out)
    p.add_argument("--val-ratio", type=float, default=0.1,
                   help="Fraction of train videos held out for validation/early stopping")
    p.add_argument("--val-seed", type=int, default=42,
                   help="Seed for the deterministic train/val video_id split")
    # Misc
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="cuda/cpu",
    )
    p.add_argument("--resume", default=None, help="Checkpoint path to resume from")
    p.add_argument("--eval-every", type=int, default=1, help="Eval every N epochs")
    p.add_argument("--log-every", type=int, default=20, help="Log every N steps")
    return p


def main():
    train(build_argparser().parse_args())


if __name__ == "__main__":
    main()
