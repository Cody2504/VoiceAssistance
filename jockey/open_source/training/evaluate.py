"""
Evaluation script for fine-tuned ViCLIP.

Computes Recall@K metrics on a held-out test set to measure
video-text retrieval quality.

Usage:
    python -m jockey.open_source.training.evaluate \
        --checkpoint ./checkpoints/viclip_finetuned/epoch_10 \
        --data_dir ./training_data \
        --test_dataset qv_highlights
"""
import argparse
import json
import logging
import os
from glob import glob

import numpy as np
import torch
import torch.nn.functional as F

log = logging.getLogger(__name__)


def evaluate_retrieval(model, test_pairs, device="cuda", max_frames=8, batch_size=32):
    """Compute Recall@1, R@5, R@10 for text→video and video→text retrieval.

    Args:
        model: ViCLIP model (already on device).
        test_pairs: List of {"video_path": str, "text": str} dicts.
        device: Torch device.
        max_frames: Max frames per video.
        batch_size: Batch size for encoding.

    Returns:
        Dict with recall metrics.
    """
    from jockey.open_source.indexer import extract_frames

    model.eval()
    video_embs = []
    text_embs = []

    log.info(f"Encoding {len(test_pairs)} test pairs...")

    for i in range(0, len(test_pairs), batch_size):
        batch = test_pairs[i:i + batch_size]

        # Encode videos
        frames_list = []
        for pair in batch:
            try:
                frames = extract_frames(pair["video_path"], 0.0, pair.get("end", 300.0), max_frames)
                frames_tensor = torch.from_numpy(frames).float().permute(0, 3, 1, 2) / 255.0
            except Exception:
                frames_tensor = torch.zeros(max_frames, 3, 224, 224)
            frames_list.append(frames_tensor)

        frames_batch = torch.stack(frames_list).to(device)
        texts = [p["text"] for p in batch]

        with torch.no_grad():
            v_emb = model.encode_video(frames_batch)
            t_emb = model.encode_text(texts)
            video_embs.append(F.normalize(v_emb, dim=-1).cpu())
            text_embs.append(F.normalize(t_emb, dim=-1).cpu())

    video_embs = torch.cat(video_embs, dim=0)  # [N, D]
    text_embs = torch.cat(text_embs, dim=0)    # [N, D]

    # Similarity matrix
    sim_matrix = text_embs @ video_embs.T  # [N, N]

    n = len(sim_matrix)
    results = {}

    for k in [1, 5, 10]:
        if k > n:
            continue

        # Text → Video retrieval
        topk_t2v = sim_matrix.topk(k, dim=1).indices
        correct_t2v = (topk_t2v == torch.arange(n).unsqueeze(1)).any(dim=1)
        r_t2v = correct_t2v.float().mean().item()

        # Video → Text retrieval
        topk_v2t = sim_matrix.T.topk(k, dim=1).indices
        correct_v2t = (topk_v2t == torch.arange(n).unsqueeze(1)).any(dim=1)
        r_v2t = correct_v2t.float().mean().item()

        results[f"t2v_R@{k}"] = round(r_t2v, 4)
        results[f"v2t_R@{k}"] = round(r_v2t, 4)

        log.info(f"  R@{k}: t2v={r_t2v:.4f}  v2t={r_v2t:.4f}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate ViCLIP retrieval performance")
    parser.add_argument("--checkpoint", required=True, help="Path to fine-tuned checkpoint")
    parser.add_argument("--data_dir", default="./training_data", help="Directory with test pairs")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max_pairs", type=int, default=1000, help="Max test pairs to evaluate")
    parser.add_argument("--max_frames", type=int, default=8)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    # Load model
    log.info(f"Loading model from {args.checkpoint}")
    try:
        from peft import AutoPeftModel
        model = AutoPeftModel.from_pretrained(args.checkpoint)
    except Exception:
        from transformers import AutoModel
        model = AutoModel.from_pretrained(args.checkpoint, trust_remote_code=True)
    model = model.to(args.device)

    # Load test pairs
    test_pairs = []
    for f in glob(os.path.join(args.data_dir, "*_pairs.jsonl")):
        with open(f) as fp:
            for line in fp:
                pair = json.loads(line)
                if os.path.isfile(pair["video_path"]):
                    test_pairs.append(pair)
                    if len(test_pairs) >= args.max_pairs:
                        break
        if len(test_pairs) >= args.max_pairs:
            break

    log.info(f"Loaded {len(test_pairs)} test pairs")

    # Evaluate
    results = evaluate_retrieval(model, test_pairs, args.device, args.max_frames)

    # Save results
    output_file = os.path.join(os.path.dirname(args.checkpoint), "eval_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    log.info(f"Results saved to {output_file}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
