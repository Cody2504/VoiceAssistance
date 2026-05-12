"""
Test the trained QDDETRHead at runtime on Charades-STA records with GT.

Loads a checkpoint, samples N random test records that have feature files,
runs `MomentLocalizer.localize` on each, and prints predicted span vs GT span
with per-record IoU and aggregate R@1@IoU=θ.

This is the *runtime* version of the eval in `qd_detr_train.py` — same numbers,
but using the inference-time entry point (MomentLocalizer) rather than the
training loop's evaluate() function. If these numbers match what the training
log reported, the inference path is wired correctly.

Usage on Colab (your paths):
    !python test_moment_localizer.py \\
        --checkpoint /content/drive/MyDrive/data/runs/qd_detr_clip/best.pt \\
        --features-dir /content/drive/MyDrive/data/features/charades \\
        --test-ann /content/drive/MyDrive/data/charades_sta_test.txt \\
        --n 30 --device cuda

On laptop CPU (slower, ~30s + ~1s/query):
    python test_moment_localizer.py \\
        --checkpoint runs/qd_detr_clip/best.pt \\
        --features-dir features/charades \\
        --test-ann data/charades_sta_test.txt \\
        --n 10 --device cpu
"""
import argparse
import logging
import os
import random
import time

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from jockey.open_source.moment_localizer import MomentLocalizer
from jockey.open_source.training.charades_sta import parse_annotations


def iou_1d(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint",   required=True)
    p.add_argument("--features-dir", required=True)
    p.add_argument("--test-ann",     required=True)
    p.add_argument("--n",     type=int, default=20, help="random records to sample")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    p.add_argument("--seed",   type=int, default=42)
    p.add_argument("--show-confidence", action="store_true",
                   help="print mean saliency per record (extra column)")
    args = p.parse_args()

    random.seed(args.seed)

    loc = MomentLocalizer(
        checkpoint_path=args.checkpoint,
        features_dir=args.features_dir,
        device=args.device,
    )

    recs = parse_annotations(args.test_ann)
    recs = [
        r for r in recs
        if os.path.isfile(os.path.join(args.features_dir, f"{r['video_id']}.npz"))
    ]
    if not recs:
        raise SystemExit(
            f"No test records have features in {args.features_dir}. "
            f"Extracted features needed for the test videos."
        )

    random.shuffle(recs)
    sample = recs[: args.n]
    print(f"\nTesting {len(sample)} records (filtered from {len(recs)} test records with features)\n")

    header = f"{'IoU':>5} | {'pred (s)':>13} | {'gt (s)':>13} | {'video':>8}"
    if args.show_confidence:
        header += f" | {'conf':>5}"
    header += " | query"
    print(header)
    print("-" * len(header) + "----")

    ious, confs, latencies = [], [], []
    for r in sample:
        t0 = time.time()
        pred = loc.localize(r["query"], r["video_id"])
        latencies.append(time.time() - t0)

        iou = iou_1d(pred.start_sec, pred.end_sec, r["start_sec"], r["end_sec"])
        ious.append(iou)
        confs.append(pred.confidence)

        row = (
            f"{iou:5.3f} | "
            f"[{pred.start_sec:4.1f}, {pred.end_sec:5.1f}] | "
            f"[{r['start_sec']:4.1f}, {r['end_sec']:5.1f}] | "
            f"{r['video_id']:>8}"
        )
        if args.show_confidence:
            row += f" | {pred.confidence:5.3f}"
        row += f" | {r['query'][:60]}"
        print(row)

    ious_a = np.array(ious)
    print()
    print("=" * 60)
    print(f"Summary on {len(ious)} records:")
    print(f"  mean IoU       : {ious_a.mean():.4f}")
    print(f"  R@1@IoU=0.3    : {(ious_a >= 0.3).mean():.4f}")
    print(f"  R@1@IoU=0.5    : {(ious_a >= 0.5).mean():.4f}")
    print(f"  R@1@IoU=0.7    : {(ious_a >= 0.7).mean():.4f}")
    print(f"  mean latency   : {np.mean(latencies)*1000:.1f} ms/query  (incl. CLIP-text)")
    if args.show_confidence:
        c = np.array(confs)
        print(f"  mean confidence: {c.mean():.4f}  (range {c.min():.2f}-{c.max():.2f})")


if __name__ == "__main__":
    main()
