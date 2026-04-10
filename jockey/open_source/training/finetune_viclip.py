"""
ViCLIP LoRA fine-tuning script.

Fine-tunes InternVideo2/ViCLIP on video-text contrastive pairs
prepared by prepare_data.py.

Usage:
    python -m jockey.open_source.training.finetune_viclip \
        --data_dir ./training_data \
        --output_dir ./checkpoints/viclip_finetuned \
        --epochs 10 \
        --batch_size 32 \
        --lr 1e-4

Requirements:
    - GPU: 1x A100 40GB (LoRA) or 2-4x A100 (full fine-tuning)
    - pip install peft torch transformers accelerate
"""
import argparse
import json
import logging
import os
from glob import glob

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

log = logging.getLogger(__name__)


class ViCLIPContrastiveDataset(Dataset):
    """Dataset that loads video-text pairs from JSONL files."""

    def __init__(self, data_dir: str, max_frames: int = 8):
        self.max_frames = max_frames
        self.pairs = []

        for jsonl_file in glob(os.path.join(data_dir, "*_pairs.jsonl")):
            log.info(f"Loading pairs from {jsonl_file}")
            with open(jsonl_file) as f:
                for line in f:
                    pair = json.loads(line)
                    if os.path.isfile(pair["video_path"]):
                        self.pairs.append(pair)

        log.info(f"Loaded {len(self.pairs)} training pairs")

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        pair = self.pairs[idx]

        try:
            from jockey.open_source.indexer import extract_frames
            frames = extract_frames(
                pair["video_path"],
                start_sec=pair.get("start", 0.0),
                end_sec=pair.get("end") or 300.0,
                max_frames=self.max_frames,
            )
        except Exception:
            frames = np.zeros((self.max_frames, 224, 224, 3), dtype=np.uint8)

        # Convert to tensor: [N, H, W, 3] → [N, 3, H, W] float [0, 1]
        frames_tensor = torch.from_numpy(frames).float().permute(0, 3, 1, 2) / 255.0

        return {
            "frames": frames_tensor,
            "text": pair["text"],
        }


def info_nce_loss(video_emb: torch.Tensor, text_emb: torch.Tensor, temperature: float = 0.07):
    """Symmetric InfoNCE contrastive loss.

    Args:
        video_emb: Normalized video embeddings [B, D].
        text_emb: Normalized text embeddings [B, D].
        temperature: Temperature scaling factor.

    Returns:
        Scalar loss.
    """
    logits = (video_emb @ text_emb.T) / temperature  # [B, B]
    labels = torch.arange(len(logits), device=logits.device)
    loss_v2t = F.cross_entropy(logits, labels)
    loss_t2v = F.cross_entropy(logits.T, labels)
    return (loss_v2t + loss_t2v) / 2


def train(args):
    """Main training loop."""
    # Load model
    log.info(f"Loading ViCLIP model: {args.model_name}")

    try:
        from internvideo2.models.viclip import ViCLIP
        model = ViCLIP.from_pretrained(args.model_name)
    except ImportError:
        from transformers import AutoModel
        model = AutoModel.from_pretrained(args.model_name, trust_remote_code=True)

    model = model.to(args.device)

    # Apply LoRA if requested
    if args.use_lora:
        from peft import LoraConfig, get_peft_model

        lora_config = LoraConfig(
            r=args.lora_rank,
            lora_alpha=args.lora_alpha,
            target_modules=["q_proj", "v_proj", "k_proj"],
            lora_dropout=0.05,
            bias="none",
        )
        model = get_peft_model(model, lora_config)
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        log.info(f"LoRA applied: {trainable:,} / {total:,} parameters trainable ({100*trainable/total:.1f}%)")

    # Dataset + DataLoader
    dataset = ViCLIPContrastiveDataset(args.data_dir, max_frames=args.max_frames)
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True,
    )

    # Optimizer
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    # Training loop
    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        num_batches = 0

        for batch in dataloader:
            frames = batch["frames"].to(args.device)  # [B, N, 3, H, W]
            texts = batch["text"]

            # Encode
            video_emb = model.encode_video(frames)       # [B, D]
            text_emb = model.encode_text(texts)           # [B, D]

            # Normalize
            video_emb = F.normalize(video_emb, dim=-1)
            text_emb = F.normalize(text_emb, dim=-1)

            # Loss
            loss = info_nce_loss(video_emb, text_emb, temperature=args.temperature)

            # Backward
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            total_loss += loss.item()
            num_batches += 1

        avg_loss = total_loss / max(num_batches, 1)
        log.info(f"Epoch {epoch+1}/{args.epochs} — loss: {avg_loss:.4f}")

        # Save checkpoint
        if (epoch + 1) % args.save_every == 0 or (epoch + 1) == args.epochs:
            checkpoint_dir = os.path.join(args.output_dir, f"epoch_{epoch+1}")
            os.makedirs(checkpoint_dir, exist_ok=True)
            if args.use_lora:
                model.save_pretrained(checkpoint_dir)
            else:
                torch.save(model.state_dict(), os.path.join(checkpoint_dir, "model.pt"))
            log.info(f"Saved checkpoint to {checkpoint_dir}")

    log.info("Training complete!")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune ViCLIP with LoRA")
    parser.add_argument("--data_dir", default="./training_data", help="Directory with *_pairs.jsonl files")
    parser.add_argument("--output_dir", default="./checkpoints/viclip_finetuned", help="Output for checkpoints")
    parser.add_argument("--model_name", default="OpenGVLab/ViCLIP-L-14", help="Pretrained model name or path")
    parser.add_argument("--device", default="cuda", help="Device to train on")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--temperature", type=float, default=0.07)
    parser.add_argument("--max_frames", type=int, default=8)
    parser.add_argument("--save_every", type=int, default=2, help="Save checkpoint every N epochs")
    # LoRA
    parser.add_argument("--use_lora", action="store_true", default=True, help="Use LoRA (default: True)")
    parser.add_argument("--no_lora", dest="use_lora", action="store_false", help="Full fine-tuning")
    parser.add_argument("--lora_rank", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    train(args)


if __name__ == "__main__":
    main()
