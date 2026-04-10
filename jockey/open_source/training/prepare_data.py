"""
Data preparation for ViCLIP fine-tuning.

Downloads and converts Molmo2 academic video datasets (QVHighlights, ActivityNet, etc.)
into (video_frames, text_query) contrastive training pairs.

Usage:
    python -m jockey.open_source.training.prepare_data --dataset qv_highlights --output_dir ./training_data
"""
import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

log = logging.getLogger(__name__)

# Add molmo2 to path if available
MOLMO2_PATH = os.environ.get("MOLMO2_PATH", os.path.expanduser("~/project/molmo2"))
if os.path.isdir(MOLMO2_PATH):
    sys.path.insert(0, MOLMO2_PATH)


SUPPORTED_DATASETS = {
    "qv_highlights": {
        "molmo_name": "qv_highlights",
        "split": "train",
        "description": "Query-Video Highlights — query→timestamp pairs, best for retrieval fine-tuning",
        "priority": "HIGH",
    },
    "activitynet": {
        "molmo_name": "activitynet_all",
        "split": "train",
        "description": "ActivityNet — dense captions aligned to video segments",
        "priority": "HIGH",
    },
    "youcook2": {
        "molmo_name": "youcook2_all",
        "split": "train",
        "description": "YouCook2 — clip-level captions for instructional video",
        "priority": "MEDIUM",
    },
    "charades_sta": {
        "molmo_name": "charades_sta_all",
        "split": "train",
        "description": "Charades-STA — temporal grounding queries",
        "priority": "MEDIUM",
    },
    "llava_video": {
        "molmo_name": "llava_video_oe_academic",
        "split": "train",
        "description": "LLaVA-Video-178K — large-scale video-text pairs",
        "priority": "LOW",
    },
}


def download_dataset(dataset_key: str):
    """Download a dataset using Molmo2's built-in downloader."""
    ds_info = SUPPORTED_DATASETS[dataset_key]
    try:
        from olmo.data.get_dataset import download_dataset_by_name
        log.info(f"Downloading '{ds_info['molmo_name']}' via Molmo2...")
        download_dataset_by_name(ds_info["molmo_name"], n_procs=8)
        log.info(f"Download complete: {dataset_key}")
    except ImportError:
        log.error(
            f"Molmo2 not found at {MOLMO2_PATH}. "
            f"Set MOLMO2_PATH env var or clone: git clone https://github.com/allenai/molmo2.git"
        )
        raise


def load_dataset(dataset_key: str):
    """Load a dataset using Molmo2's dataset loader."""
    ds_info = SUPPORTED_DATASETS[dataset_key]
    from olmo.data.get_dataset import get_dataset_by_name
    return get_dataset_by_name(ds_info["molmo_name"], ds_info["split"])


def convert_to_training_pairs(
    dataset_key: str,
    output_dir: str,
    max_examples: int = None,
) -> str:
    """Convert a Molmo2 dataset to ViCLIP contrastive training format.

    Output format (JSONL):
    {"video_path": "/path/to/video.mp4", "text": "query text", "start": 0.0, "end": 10.0}

    Args:
        dataset_key: Key from SUPPORTED_DATASETS.
        output_dir: Where to write the output JSONL file.
        max_examples: Maximum number of examples to convert (None = all).

    Returns:
        Path to the output JSONL file.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{dataset_key}_pairs.jsonl")

    log.info(f"Loading dataset '{dataset_key}'...")
    dataset = load_dataset(dataset_key)

    log.info(f"Converting {len(dataset)} examples to training pairs...")
    count = 0

    with open(output_file, "w") as f:
        rng = np.random.RandomState(42)
        for i in range(len(dataset)):
            if max_examples and count >= max_examples:
                break

            try:
                example = dataset.get(i, rng)
            except Exception as e:
                log.warning(f"Skipping example {i}: {e}")
                continue

            video_path = example.get("video", "")
            if not video_path or not os.path.isfile(video_path):
                continue

            # Extract text — different datasets have different fields
            text = ""
            if "message_list" in example:
                for msg in example["message_list"]:
                    if "question" in msg:
                        text = msg["question"]
                        break
                    elif "text" in msg:
                        text = msg["text"]
                        break
            elif "question" in example:
                text = example["question"]
            elif "answer" in example:
                text = example["answer"]

            if not text:
                continue

            # Get clip bounds if available
            metadata = example.get("metadata", {})
            pair = {
                "video_path": video_path,
                "text": text,
                "start": metadata.get("start", 0.0),
                "end": metadata.get("end", None),
                "dataset": dataset_key,
            }

            f.write(json.dumps(pair) + "\n")
            count += 1

    log.info(f"Wrote {count} training pairs to {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Prepare training data for ViCLIP fine-tuning")
    parser.add_argument("--dataset", choices=list(SUPPORTED_DATASETS.keys()), required=True,
                        help="Dataset to prepare")
    parser.add_argument("--output_dir", default="./training_data", help="Output directory")
    parser.add_argument("--max_examples", type=int, default=None, help="Max examples to convert")
    parser.add_argument("--download", action="store_true", help="Download dataset first")
    parser.add_argument("--list", action="store_true", help="List all supported datasets")

    args = parser.parse_args()

    if args.list:
        print("\nSupported datasets for ViCLIP fine-tuning:\n")
        for key, info in SUPPORTED_DATASETS.items():
            print(f"  {key:20s} [{info['priority']:6s}] {info['description']}")
        return

    logging.basicConfig(level=logging.INFO)

    if args.download:
        download_dataset(args.dataset)

    convert_to_training_pairs(args.dataset, args.output_dir, args.max_examples)


if __name__ == "__main__":
    main()
