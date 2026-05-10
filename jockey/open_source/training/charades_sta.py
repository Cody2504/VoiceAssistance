"""
Charades-STA dataset — annotation parser, downloader, and PyTorch Dataset.

Annotation format (one query per line):
    VIDEO_ID start_sec end_sec##query_text

Example:
    AO8RW 0.0 6.9##person turn a light on.
    AO8RW 24.3 30.4##person flipped the light switch near the door.

Pipeline assumed:
    1. Download Charades-STA annotation files (train/test).
    2. Download Charades videos (manual, registration required:
       https://prior.allenai.org/projects/charades).
    3. Run `feature_extractor` / `batch_extract` over all videos → `<features_dir>/<vid>.npz`.
    4. Run `precompute_queries` to embed unique queries → `<query_cache>.npz`.
    5. Use `CharadesSTADataset` for training.

Usage:
    from jockey.open_source.training.charades_sta import (
        download_annotations, parse_annotations,
        CharadesSTADataset, grounding_collate,
    )

    train_ann = parse_annotations("charades_sta_train.txt")
    ds = CharadesSTADataset(
        annotations=train_ann,
        features_dir="features/charades/",
        query_cache_path="features/charades/query_emb.npz",
        max_shots=64,
    )
    loader = torch.utils.data.DataLoader(
        ds, batch_size=16, shuffle=True, collate_fn=grounding_collate,
    )
"""
import logging
import os
import urllib.request
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset

from jockey.open_source.training.feature_extractor import ShotFeatures

log = logging.getLogger(__name__)


# Canonical mirrors. Verify before each thesis run; mirrors do change.
DEFAULT_ANNOTATION_URLS: Dict[str, str] = {
    "train": (
        "https://raw.githubusercontent.com/jiyanggao/TALL/master/"
        "exp_data/Charades_v1.0_localization/charades_sta_train.txt"
    ),
    "test": (
        "https://raw.githubusercontent.com/jiyanggao/TALL/master/"
        "exp_data/Charades_v1.0_localization/charades_sta_test.txt"
    ),
}


# ---------------------------------------------------------------------------
# Annotation IO
# ---------------------------------------------------------------------------

def download_annotations(
    out_dir: str,
    urls: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Download Charades-STA train/test annotation .txt files.

    Returns a {split: local_path} mapping. If a file already exists, it is reused.
    """
    urls = urls or DEFAULT_ANNOTATION_URLS
    os.makedirs(out_dir, exist_ok=True)
    paths: Dict[str, str] = {}
    for split, url in urls.items():
        local = os.path.join(out_dir, f"charades_sta_{split}.txt")
        if not os.path.isfile(local):
            log.info(f"Downloading Charades-STA {split} annotations: {url}")
            try:
                urllib.request.urlretrieve(url, local)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to download {url}: {e}\n"
                    f"Mirror may have moved. Try the official source: "
                    f"https://github.com/jiyanggao/TALL"
                ) from e
        else:
            log.info(f"Found existing {split} annotations: {local}")
        paths[split] = local
    return paths


def parse_annotations(path: str) -> List[Dict]:
    """Parse a Charades-STA annotation file into a list of records.

    Each record: {video_id, start_sec, end_sec, query, line_idx}.
    Skips malformed lines with a warning.
    """
    records: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                head, query = line.split("##", 1)
                parts = head.strip().split()
                if len(parts) != 3:
                    raise ValueError(f"expected 3 fields before ##, got {len(parts)}")
                video_id, s_str, e_str = parts
                records.append({
                    "video_id": video_id,
                    "start_sec": float(s_str),
                    "end_sec": float(e_str),
                    "query": query.strip(),
                    "line_idx": i,
                })
            except Exception as e:
                log.warning(f"  skip {path}:{i+1}: {e}")
    log.info(f"Parsed {len(records)} records from {path}")
    return records


def unique_queries(records: List[Dict]) -> List[str]:
    """Return deduplicated list of query strings (preserves first-seen order)."""
    seen = set()
    out = []
    for r in records:
        q = r["query"]
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


# ---------------------------------------------------------------------------
# GT relevance / boundary helpers
# ---------------------------------------------------------------------------

def compute_shot_relevance(
    shot_boundaries: np.ndarray,    # [N, 2] (start, end) in seconds
    moment_start: float,
    moment_end: float,
    overlap_threshold: float = 0.5,
) -> np.ndarray:
    """Per-shot binary relevance.

    Shot is positive if (intersection / shot_duration) >= overlap_threshold.
    If no shot meets the threshold, the shot with the most overlap is forced positive.

    Returns float32 array [N] in {0.0, 1.0}.
    """
    n = shot_boundaries.shape[0]
    rel = np.zeros(n, dtype=np.float32)
    overlaps = np.zeros(n, dtype=np.float32)

    for i, (s, e) in enumerate(shot_boundaries):
        inter = max(0.0, min(float(e), moment_end) - max(float(s), moment_start))
        shot_dur = max(1e-6, float(e) - float(s))
        ratio = inter / shot_dur
        overlaps[i] = inter
        if ratio >= overlap_threshold:
            rel[i] = 1.0

    if rel.sum() == 0 and n > 0 and overlaps.max() > 0:
        rel[int(np.argmax(overlaps))] = 1.0

    return rel


def normalize_boundary(
    moment_start: float, moment_end: float, video_duration: float
) -> np.ndarray:
    """Normalize boundary to [0, 1] by video duration. Returns float32 [2]."""
    d = max(1e-6, float(video_duration))
    s = float(np.clip(moment_start / d, 0.0, 1.0))
    e = float(np.clip(moment_end / d, 0.0, 1.0))
    if e < s:
        s, e = e, s
    return np.array([s, e], dtype=np.float32)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class CharadesSTADataset(Dataset):
    """PyTorch Dataset over precomputed features + cached query embeddings.

    Each item yields a dict (tensors are torch.float32 unless noted):
        visual         [N, V]
        audio          [N, A]
        caption        [N, C]
        query          [Q]
        global_emb     [Q]
        gt_relevance   [N]      in {0, 1}
        gt_boundary    [2]      normalized to [0, 1] by video duration
        num_shots      int
        video_id       str
        query_text     str
    """

    def __init__(
        self,
        annotations: List[Dict],
        features_dir: str,
        query_cache_path: str,
        max_shots: int = 64,
        overlap_threshold: float = 0.5,
        require_features: bool = True,
        cache_features_in_ram: bool = False,
    ):
        self.features_dir = features_dir
        self.max_shots = max_shots
        self.overlap_threshold = overlap_threshold
        self.cache_features_in_ram = cache_features_in_ram
        self._ram_cache: Dict[str, ShotFeatures] = {}

        # Filter annotations down to ones whose feature file exists
        self.annotations: List[Dict] = []
        missing = 0
        for r in annotations:
            fpath = self._feature_path(r["video_id"])
            if os.path.isfile(fpath):
                self.annotations.append(r)
            else:
                missing += 1
        if missing > 0:
            msg = f"{missing}/{len(annotations)} annotations skipped — missing feature .npz"
            if require_features:
                log.warning(msg)
            else:
                log.info(msg)

        # Load query embedding cache
        if not os.path.isfile(query_cache_path):
            raise FileNotFoundError(
                f"Query embedding cache not found: {query_cache_path}. "
                f"Build it with `precompute_queries.py` first."
            )
        cache = np.load(query_cache_path, allow_pickle=True)
        self.query_to_emb: Dict[str, np.ndarray] = {
            str(k): v for k, v in zip(cache["queries"], cache["embeddings"])
        }
        log.info(
            f"CharadesSTADataset: {len(self.annotations)} examples, "
            f"{len(self.query_to_emb)} cached query embeddings."
        )

    def _feature_path(self, video_id: str) -> str:
        return os.path.join(self.features_dir, f"{video_id}.npz")

    def _load_features(self, video_id: str) -> ShotFeatures:
        if video_id in self._ram_cache:
            return self._ram_cache[video_id]
        feats = ShotFeatures.load(self._feature_path(video_id))
        if self.cache_features_in_ram:
            self._ram_cache[video_id] = feats
        return feats

    def __len__(self) -> int:
        return len(self.annotations)

    def __getitem__(self, idx: int) -> Dict:
        r = self.annotations[idx]
        feats = self._load_features(r["video_id"])
        query = r["query"]

        if query not in self.query_to_emb:
            raise KeyError(
                f"Query not in cache: '{query[:60]}...' "
                f"(rebuild query cache with current train+test splits)"
            )

        # Truncate to max_shots if needed
        n = min(feats.num_shots, self.max_shots)
        sb = feats.shot_boundaries[:n]
        visual = feats.visual_features[:n]
        audio = feats.audio_features[:n]
        caption = feats.caption_features[:n]

        gt_rel = compute_shot_relevance(
            sb, r["start_sec"], r["end_sec"], self.overlap_threshold
        )
        gt_bnd = normalize_boundary(r["start_sec"], r["end_sec"], feats.duration)

        return {
            "visual": torch.from_numpy(visual).float(),
            "audio": torch.from_numpy(audio).float(),
            "caption": torch.from_numpy(caption).float(),
            "query": torch.from_numpy(self.query_to_emb[query]).float(),
            "global_emb": torch.from_numpy(feats.global_metadata_emb).float(),
            "gt_relevance": torch.from_numpy(gt_rel),
            "gt_boundary": torch.from_numpy(gt_bnd),
            "num_shots": n,
            "video_id": r["video_id"],
            "query_text": query,
        }


def grounding_collate(batch: List[Dict]) -> Dict:
    """Pad variable-length shot sequences. Returns batched tensors + shot_mask."""
    B = len(batch)
    max_n = max(b["num_shots"] for b in batch)
    v_dim = batch[0]["visual"].shape[1]
    a_dim = batch[0]["audio"].shape[1]
    c_dim = batch[0]["caption"].shape[1]

    visual = torch.zeros(B, max_n, v_dim)
    audio = torch.zeros(B, max_n, a_dim)
    caption = torch.zeros(B, max_n, c_dim)
    gt_rel = torch.zeros(B, max_n)
    shot_mask = torch.zeros(B, max_n, dtype=torch.bool)

    for i, b in enumerate(batch):
        n = b["num_shots"]
        visual[i, :n] = b["visual"]
        audio[i, :n] = b["audio"]
        caption[i, :n] = b["caption"]
        gt_rel[i, :n] = b["gt_relevance"]
        shot_mask[i, :n] = True

    return {
        "visual": visual,
        "audio": audio,
        "caption": caption,
        "query": torch.stack([b["query"] for b in batch], dim=0),
        "global_emb": torch.stack([b["global_emb"] for b in batch], dim=0),
        "gt_relevance": gt_rel,
        "gt_boundary": torch.stack([b["gt_boundary"] for b in batch], dim=0),
        "shot_mask": shot_mask,
        "num_shots": torch.tensor([b["num_shots"] for b in batch], dtype=torch.long),
        "video_id": [b["video_id"] for b in batch],
        "query_text": [b["query_text"] for b in batch],
    }
