"""
Precompute Query Embeddings — cache text-embedding-3-large embeddings for unique queries.

Run once after parsing Charades-STA annotations. Avoids hitting the API during training.

Usage:
    python -m jockey.open_source.training.precompute_queries \\
        --annotations data/charades_sta_train.txt data/charades_sta_test.txt \\
        --out features/charades/query_emb.npz

Cached format (.npz):
    queries     — object array of strings
    embeddings  — float32 [num_queries, text_dim]

Incremental: if --out exists, only new queries are embedded and merged in.
"""
import argparse
import logging
import os
import time
from typing import Dict, List

import numpy as np

from jockey.open_source.config import config as default_config
from jockey.open_source.training.charades_sta import (
    parse_annotations as parse_charades,
    unique_queries,
)
from jockey.open_source.training.youcook2 import parse_annotations as parse_youcook2

log = logging.getLogger(__name__)


def load_existing_cache(path: str) -> Dict[str, np.ndarray]:
    if not os.path.isfile(path):
        return {}
    data = np.load(path, allow_pickle=True)
    return {str(q): v for q, v in zip(data["queries"], data["embeddings"])}


def save_cache(cache: Dict[str, np.ndarray], path: str) -> None:
    out_dir = os.path.dirname(os.path.abspath(path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    queries = np.array(list(cache.keys()), dtype=object)
    embeddings = np.stack(list(cache.values()), axis=0).astype(np.float32)
    np.savez_compressed(path, queries=queries, embeddings=embeddings)


def _parse_any(path: str) -> List[Dict]:
    """Auto-detect format: .txt → Charades-STA; .json → YouCook2."""
    if path.lower().endswith(".json"):
        return parse_youcook2(path)
    return parse_charades(path)


def collect_unique_queries(
    annotation_paths: List[str],
    features_dir_filter: str = "",
) -> List[str]:
    """Collect unique queries across annotation files.

    If `features_dir_filter` is set, only keep queries whose video_id has a
    matching <video_id>.npz in that directory. Useful for sanity-check runs
    where you've extracted features for a subset of videos.
    """
    all_records = []
    for p in annotation_paths:
        all_records.extend(_parse_any(p))

    if features_dir_filter:
        available = {
            os.path.splitext(f)[0]
            for f in os.listdir(features_dir_filter)
            if f.endswith(".npz") and not f.startswith("query")
        }
        before = len(all_records)
        all_records = [r for r in all_records if r["video_id"] in available]
        log.info(
            f"Features-filter: kept {len(all_records)}/{before} records "
            f"({len(available)} videos with features in {features_dir_filter})"
        )

    return unique_queries(all_records)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    p = argparse.ArgumentParser(description="Precompute Charades-STA query embeddings.")
    p.add_argument(
        "--annotations", nargs="+", required=True,
        help="One or more Charades-STA annotation .txt files (train + test).",
    )
    p.add_argument("--out", required=True, help="Output .npz cache path.")
    p.add_argument("--checkpoint-every", type=int, default=100,
                   help="Save cache to disk every N queries.")
    p.add_argument("--limit", type=int, default=None, help="Embed at most N new queries.")
    p.add_argument(
        "--features-dir-filter",
        default="",
        help="Only embed queries whose video_id has a feature .npz in this dir "
             "(useful for sanity-check runs over a small subset of videos).",
    )
    args = p.parse_args()

    queries = collect_unique_queries(args.annotations, features_dir_filter=args.features_dir_filter)
    log.info(f"{len(queries)} unique queries across {len(args.annotations)} annotation files")

    cache = load_existing_cache(args.out)
    log.info(f"Existing cache: {len(cache)} queries")

    todo = [q for q in queries if q not in cache]
    if args.limit is not None:
        todo = todo[: args.limit]
    log.info(f"To embed: {len(todo)} new queries")

    if not todo:
        save_cache(cache, args.out)
        log.info(f"Nothing to do. Cache saved at {args.out} ({len(cache)} queries)")
        return

    from jockey.open_source.search import TextEmbedder

    embedder = TextEmbedder(
        api_key=default_config.openrouter_api_key,
        model=default_config.text_embedding_model,
        base_url=default_config.openrouter_base_url,
    )

    t0 = time.time()
    n_ok = n_fail = 0
    for i, q in enumerate(todo, 1):
        try:
            emb = embedder.encode(q).astype(np.float32)
            cache[q] = emb
            n_ok += 1
        except Exception as e:
            log.warning(f"  failed '{q[:60]}...': {e}")
            n_fail += 1

        if i % args.checkpoint_every == 0:
            save_cache(cache, args.out)
            elapsed = time.time() - t0
            log.info(
                f"[{i}/{len(todo)}] checkpoint saved "
                f"({elapsed:.1f}s, ok={n_ok} fail={n_fail})"
            )

    save_cache(cache, args.out)
    elapsed = time.time() - t0
    log.info(
        f"Done. cached={len(cache)} new_ok={n_ok} new_fail={n_fail} "
        f"elapsed={elapsed:.1f}s → {args.out}"
    )


if __name__ == "__main__":
    main()
