"""
Train QDDETRHead on InternVideo2 features (Charades-STA).

Mirrors `train.py` but uses:
    - QDDETRHead (cross-attention query injection) instead of GroundingHead
    - qd_detr_loss instead of grounding_loss
    - Visual-only inputs (audio / caption / global_emb ignored — IV2 unified)

Auto-discovers `visual_dim` from the first batch so the head matches whatever
InternVideo2 variant produced the features (1B → 768-d typical, but the
checkpoint can vary).

Usage:
    python -m jockey.open_source.training.qd_detr_train \\
        --features-dir features/iv2_charades/ \\
        --train-ann   data/charades_sta_train.txt \\
        --test-ann    data/charades_sta_test.txt \\
        --query-cache features/iv2_charades/query_emb_iv2.npz \\
        --out-dir     runs/qd_detr_iv2/

Outputs (in --out-dir):
    config.json, train_log.csv, val_log.csv, best.pt, last.pt, test_metrics.json
"""
from __future__ import annotations

import argparse
import csv
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
from jockey.open_source.training.qd_detr_head import (
    QDDETRConfig,
    QDDETRHead,
    qd_detr_loss,
    recall_at_iou,
    mean_iou,
)
# Reuse the hash-stable video-level split from train.py — same correctness
# guarantee (no leakage across train/val) and same seed semantics.
from jockey.open_source.training.train import (
    set_seed,
    split_train_val,
    cosine_warmup_lr,
    to_device,
    open_csv_logger,
)

log = logging.getLogger(__name__)


def save_checkpoint(path, model, optimizer, epoch, best_r05, cfg: QDDETRConfig) -> None:
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "epoch": epoch,
            "best_r05": best_r05,
            "config": asdict(cfg),
            "head_class": "QDDETRHead",
        },
        path,
    )


@torch.no_grad()
def evaluate(model: QDDETRHead, loader: DataLoader, device: str) -> Dict[str, float]:
    model.eval()
    all_pred, all_gt = [], []
    for batch in loader:
        batch = to_device(batch, device)
        _, bnd = model(
            visual=batch["visual"], query=batch["query"], shot_mask=batch["shot_mask"],
        )
        all_pred.append(bnd.cpu())
        all_gt.append(batch["gt_boundary"].cpu())
    if not all_pred:
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


def _infer_dims(loader: DataLoader) -> tuple:
    """Peek the first batch to discover visual_dim and query_dim at runtime.

    Required because InternVideo2 variants can output 768 (Stage2_1B CLIP-aligned)
    or other sizes — and you don't want to hardcode it in three places.
    """
    sample = next(iter(loader))
    v_dim = int(sample["visual"].shape[-1])
    q_dim = int(sample["query"].shape[-1])
    return v_dim, q_dim


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

    # Datasets
    all_train_recs = parse_annotations(args.train_ann)
    test_recs = parse_annotations(args.test_ann)
    train_recs, val_recs = split_train_val(all_train_recs, args.val_ratio, args.val_seed)
    log.info(
        f"Split (by video_id, seed={args.val_seed}, val_ratio={args.val_ratio}): "
        f"train={len(train_recs)} val={len(val_recs)} test={len(test_recs)} "
        f"(pre-feature-existence-filter)"
    )
    if not train_recs:
        raise RuntimeError("No training records after train/val split.")

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

    # Discover input dims from the actual features
    v_dim, q_dim = _infer_dims(train_loader)
    log.info(f"Runtime dims: visual_dim={v_dim}  query_dim={q_dim}")
    if v_dim != q_dim:
        log.warning(
            f"visual_dim ({v_dim}) != query_dim ({q_dim}). QD-DETR cross-attention "
            f"projects both to hidden_dim so this still trains, but the cross-attn "
            f"loses 'same-space dot-product' geometric prior. Double-check that "
            f"queries were embedded with the SAME backbone's text tower as the "
            f"visual features."
        )

    cfg = QDDETRConfig(
        visual_dim=v_dim,
        query_dim=q_dim,
        hidden_dim=args.hidden_dim,
        num_self_layers=args.num_self_layers,
        num_heads=args.num_heads,
        max_shots=args.max_shots,
        dropout=args.dropout,
        use_moment_query=not args.no_moment_query,
    )
    model = QDDETRHead(cfg).to(args.device)
    log.info(
        f"QDDETRHead: {model.num_trainable_params()/1e6:.2f}M params, "
        f"hidden={cfg.hidden_dim} self_layers={cfg.num_self_layers} heads={cfg.num_heads}"
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = args.epochs * len(train_loader)
    warmup_steps = int(total_steps * args.warmup_ratio)

    use_amp = args.mixed_precision and args.device == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_amp else None

    start_epoch = 0
    best_r05 = -1.0
    if args.resume and os.path.isfile(args.resume):
        ckpt = torch.load(args.resume, map_location=args.device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        start_epoch = ckpt["epoch"] + 1
        best_r05 = ckpt.get("best_r05", 0.0)
        log.info(f"Resumed from {args.resume} at epoch {start_epoch}, best R@0.5={best_r05:.4f}")

    train_log_f = open_csv_logger(
        os.path.join(args.out_dir, "train_log.csv"),
        "epoch,step,loss,sal,l1,iou_loss,mIoU,lr",
    )
    val_log_f = open_csv_logger(
        os.path.join(args.out_dir, "val_log.csv"),
        "epoch,r03,r05,r07,mIoU",
    )

    if args.add_epochs is not None and args.add_epochs > 0:
        target_epochs = start_epoch + args.add_epochs
        use_lr_schedule = False
        log.info(
            f"--add-epochs {args.add_epochs}: epochs {start_epoch}..{target_epochs - 1}, "
            f"constant LR = {args.lr:g}"
        )
    else:
        target_epochs = args.epochs
        use_lr_schedule = True

    global_step = start_epoch * len(train_loader)

    for epoch in range(start_epoch, target_epochs):
        model.train()
        t_ep = time.time()
        for step, batch in enumerate(train_loader):
            batch = to_device(batch, args.device)

            lr = (
                cosine_warmup_lr(global_step, total_steps, warmup_steps, args.lr)
                if use_lr_schedule else args.lr
            )
            for pg in optimizer.param_groups:
                pg["lr"] = lr

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with torch.amp.autocast(device_type="cuda"):
                    sal_logits, bnd = model(
                        visual=batch["visual"],
                        query=batch["query"],
                        shot_mask=batch["shot_mask"],
                    )
                    losses = qd_detr_loss(
                        sal_logits, bnd,
                        batch["gt_relevance"], batch["gt_boundary"],
                        shot_mask=batch["shot_mask"],
                        w_sal=args.w_sal, w_l1=args.w_l1, w_iou=args.w_iou,
                    )
                scaler.scale(losses["total"]).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
                scaler.step(optimizer)
                scaler.update()
            else:
                sal_logits, bnd = model(
                    visual=batch["visual"],
                    query=batch["query"],
                    shot_mask=batch["shot_mask"],
                )
                losses = qd_detr_loss(
                    sal_logits, bnd,
                    batch["gt_relevance"], batch["gt_boundary"],
                    shot_mask=batch["shot_mask"],
                    w_sal=args.w_sal, w_l1=args.w_l1, w_iou=args.w_iou,
                )
                losses["total"].backward()
                nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
                optimizer.step()

            if global_step % args.log_every == 0:
                log.info(
                    f"ep {epoch:3d} step {step:5d}/{len(train_loader)}  "
                    f"loss={losses['total'].item():.4f}  "
                    f"sal={losses['sal'].item():.4f}  "
                    f"l1={losses['l1'].item():.4f}  "
                    f"iou_l={losses['iou_loss'].item():.4f}  "
                    f"mIoU={losses['mIoU'].item():.4f}  lr={lr:.2e}"
                )
            train_log_f.write(
                f"{epoch},{global_step},"
                f"{losses['total'].item():.6f},{losses['sal'].item():.6f},"
                f"{losses['l1'].item():.6f},{losses['iou_loss'].item():.6f},"
                f"{losses['mIoU'].item():.6f},{lr:.6e}\n"
            )
            train_log_f.flush()
            global_step += 1

        if (epoch + 1) % args.eval_every == 0 or epoch == target_epochs - 1:
            metrics = evaluate(model, val_loader, args.device)
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

        save_checkpoint(
            os.path.join(args.out_dir, "last.pt"),
            model, optimizer, epoch, best_r05, cfg,
        )
        log.info(f"epoch {epoch} done in {time.time()-t_ep:.1f}s")

    train_log_f.close()
    val_log_f.close()
    log.info(f"Training complete. Best val R@1@IoU=0.5 = {best_r05:.4f}")

    # Final test
    best_path = os.path.join(args.out_dir, "best.pt")
    last_path = os.path.join(args.out_dir, "last.pt")
    ckpt_path = best_path if os.path.isfile(best_path) else last_path
    if os.path.isfile(ckpt_path):
        log.info(f"Loading {os.path.basename(ckpt_path)} for final test eval...")
        ckpt = torch.load(ckpt_path, map_location=args.device)
        model.load_state_dict(ckpt["model"])
        test_metrics = evaluate(model, test_loader, args.device)
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
    p = argparse.ArgumentParser(description="Train QDDETRHead on InternVideo2 features.")
    # Data
    p.add_argument("--features-dir", required=True)
    p.add_argument("--train-ann", required=True)
    p.add_argument("--test-ann", required=True)
    p.add_argument("--query-cache", required=True)
    p.add_argument("--out-dir", required=True)
    # Architecture (visual_dim / query_dim discovered at runtime)
    p.add_argument("--hidden-dim", type=int, default=256)
    p.add_argument("--num-self-layers", type=int, default=2)
    p.add_argument("--num-heads", type=int, default=8)
    p.add_argument("--max-shots", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument(
        "--no-moment-query",
        action="store_true",
        help="Disable DETR-style moment query; mean-pool encoded clips instead. "
             "Mostly useful as an ablation: 'how much does the moment query buy us?'",
    )
    # Optimization
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--add-epochs", type=int, default=None)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--warmup-ratio", type=float, default=0.05)
    p.add_argument("--grad-clip", type=float, default=1.0)
    p.add_argument("--w-sal", type=float, default=1.0)
    p.add_argument("--w-l1", type=float, default=10.0)
    p.add_argument("--w-iou", type=float, default=1.0)
    p.add_argument("--mixed-precision", action="store_true")
    # Split
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--val-seed", type=int, default=42)
    # Misc
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--resume", default=None)
    p.add_argument("--eval-every", type=int, default=1)
    p.add_argument("--log-every", type=int, default=20)
    return p


def main():
    train(build_argparser().parse_args())


if __name__ == "__main__":
    main()
