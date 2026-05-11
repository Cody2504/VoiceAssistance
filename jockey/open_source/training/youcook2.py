"""
YouCook2 dataset — auxiliary benchmark for the caption-modality ablation.

Charades-STA is visual-dominant (silent indoor activities). YouCook2 is the opposite:
~2k cooking videos with rich spoken narration, so ASR transcripts carry real signal
and the caption modality of our tri-modal fusion has something to contribute.

Annotation format (official YouCook2 JSON):

    {
      "database": {
        "<video_id>": {
          "duration": float,
          "subset": "training" | "validation",
          "annotations": [
            {"id": int, "sentence": str, "segment": [start_sec, end_sec]},
            ...
          ],
          "recipe_type": str,
          "video_url": str
        }
      }
    }

Pipeline (mirrors `charades_sta.py`):
    1. download_annotations(out_dir) — fetches official tarball from Michigan host.
    2. download_videos(records, out_dir) — uses yt-dlp on the video_url fields
       (lossy; ~20-30% of YouTube videos have been deleted over the years — normal).
    3. batch_extract over the videos with --uniform-window-sec 2.0.
    4. precompute_queries on the unique sentences.
    5. YouCook2Dataset wraps everything for training/eval.

The Dataset returns the same dict schema as CharadesSTADataset, so it slots into the
existing `grounding_collate`, `GroundingHead`, and `train.py` without any wrapper code.
"""
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from typing import Dict, List, Optional

import numpy as np
import torch
from torch.utils.data import Dataset

from jockey.open_source.training.charades_sta import (
    compute_shot_relevance,
    normalize_boundary,
)
from jockey.open_source.training.feature_extractor import ShotFeatures

log = logging.getLogger(__name__)


DEFAULT_ANNOTATION_TARBALL_URL = (
    "http://youcook2.eecs.umich.edu/static/YouCookII/"
    "youcookii_annotations_trainval.tar.gz"
)


# ---------------------------------------------------------------------------
# Annotation IO
# ---------------------------------------------------------------------------

def download_annotations(out_dir: str, url: str = DEFAULT_ANNOTATION_TARBALL_URL) -> str:
    """Download + extract the YouCook2 annotation tarball.

    Returns the path to `youcookii_annotations_trainval.json`. Caches by reusing
    an existing extracted JSON.
    """
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "youcookii_annotations_trainval.json")
    if os.path.isfile(json_path) and os.path.getsize(json_path) > 1024:
        log.info(f"Found existing YouCook2 annotations: {json_path}")
        return json_path

    log.info(f"Downloading YouCook2 annotations from: {url}")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tf:
        tarball = tf.name
    try:
        urllib.request.urlretrieve(url, tarball)
        log.info(f"  downloaded ({os.path.getsize(tarball)/1024:.1f} KB), extracting...")
        with tarfile.open(tarball, "r:gz") as t:
            t.extractall(out_dir)
        # The tarball may extract into a nested directory; find the JSON.
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f == "youcookii_annotations_trainval.json":
                    found = os.path.join(root, f)
                    if found != json_path:
                        shutil.move(found, json_path)
                    return json_path
        raise RuntimeError(
            "Tarball extracted but youcookii_annotations_trainval.json was not found. "
            f"Check {out_dir}."
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to download/extract YouCook2 annotations from {url}: {e}\n"
            f"Manual download options:\n"
            f"  1. http://youcook2.eecs.umich.edu/download (official, registration may be needed)\n"
            f"  2. https://github.com/LuoweiZhou/ProcNets-YouCook2 (original author repo)\n"
            f"Save the JSON to: {json_path}"
        ) from e
    finally:
        if os.path.isfile(tarball):
            os.remove(tarball)


def parse_annotations(json_path: str, subset: Optional[str] = None) -> List[Dict]:
    """Parse YouCook2 annotations into a flat list of records.

    Args:
        json_path: Path to youcookii_annotations_trainval.json
        subset:    'training', 'validation', or None for both

    Each record: {video_id, start_sec, end_sec, query, recipe_type, duration, video_url}.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = data.get("database", data)  # some mirrors flatten to top-level
    records: List[Dict] = []
    for video_id, meta in db.items():
        if subset is not None and meta.get("subset") != subset:
            continue
        duration = float(meta.get("duration", 0.0))
        recipe = meta.get("recipe_type", "")
        url = meta.get("video_url", "")
        for ann in meta.get("annotations", []):
            seg = ann.get("segment", [0, 0])
            sent = (ann.get("sentence") or "").strip()
            if not sent or len(seg) != 2:
                continue
            records.append({
                "video_id": video_id,
                "start_sec": float(seg[0]),
                "end_sec": float(seg[1]),
                "query": sent,
                "recipe_type": recipe,
                "duration": duration,
                "video_url": url,
                "subset": meta.get("subset", ""),
            })

    log.info(
        f"Parsed {len(records)} YouCook2 records from {json_path}"
        + (f" (subset={subset})" if subset else "")
    )
    return records


def unique_queries(records: List[Dict]) -> List[str]:
    """Deduplicate query strings (preserves first-seen order)."""
    seen = set()
    out = []
    for r in records:
        q = r["query"]
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


# ---------------------------------------------------------------------------
# Video download via yt-dlp (videos are hosted on YouTube)
# ---------------------------------------------------------------------------

def unique_video_meta(records: List[Dict]) -> List[Dict]:
    """One row per video_id with (video_id, video_url, recipe_type, duration)."""
    seen = set()
    out = []
    for r in records:
        if r["video_id"] in seen:
            continue
        seen.add(r["video_id"])
        out.append({
            "video_id": r["video_id"],
            "video_url": r["video_url"],
            "recipe_type": r["recipe_type"],
            "duration": r["duration"],
        })
    return out


def download_videos(
    records: List[Dict],
    out_dir: str,
    yt_dlp_bin: str = "yt-dlp",
    format_str: str = "best[height<=480]/best",
    skip_existing: bool = True,
    limit: Optional[int] = None,
) -> Dict[str, str]:
    """Download YouCook2 videos via yt-dlp using the video_url field.

    YouCook2 distributes only annotations; videos are on YouTube and a fraction (~20-30%)
    have been removed over time. Failures are logged and counted, not fatal.

    Returns a {video_id: local_path} mapping for the successfully downloaded videos.
    """
    if shutil.which(yt_dlp_bin) is None:
        raise RuntimeError(
            f"`{yt_dlp_bin}` not found. Install with `pip install yt-dlp` and retry."
        )

    os.makedirs(out_dir, exist_ok=True)
    metas = unique_video_meta(records)
    if limit is not None:
        metas = metas[:limit]
    log.info(f"Downloading {len(metas)} YouCook2 videos to {out_dir}")

    ok: Dict[str, str] = {}
    n_skip = n_fail = 0
    for i, m in enumerate(metas, 1):
        vid = m["video_id"]
        out_template = os.path.join(out_dir, f"{vid}.%(ext)s")
        # If an .mp4 (or other) already exists for this id, skip.
        existing = [
            os.path.join(out_dir, f)
            for f in os.listdir(out_dir)
            if f.startswith(vid + ".") and not f.endswith(".part")
        ]
        if skip_existing and existing:
            ok[vid] = existing[0]
            n_skip += 1
            continue
        url = m["video_url"]
        if not url:
            log.warning(f"[{i}/{len(metas)}] {vid}: no video_url")
            n_fail += 1
            continue

        cmd = [
            yt_dlp_bin,
            "-f", format_str,
            "--no-warnings",
            "--quiet",
            "--no-playlist",
            "-o", out_template,
            url,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            picked = [
                os.path.join(out_dir, f)
                for f in os.listdir(out_dir)
                if f.startswith(vid + ".") and not f.endswith(".part")
            ]
            if picked:
                ok[vid] = picked[0]
                log.info(f"[{i}/{len(metas)}] {vid}: OK ({picked[0]})")
            else:
                log.warning(f"[{i}/{len(metas)}] {vid}: download completed but file not found")
                n_fail += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning(f"[{i}/{len(metas)}] {vid}: yt-dlp failed ({type(e).__name__})")
            n_fail += 1

    log.info(
        f"YouCook2 video download done. ok={len(ok)} skip={n_skip} fail={n_fail} "
        f"(deletions from YouTube are normal)"
    )
    return ok


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class YouCook2Dataset(Dataset):
    """Same schema as CharadesSTADataset → drop-in compatible with grounding_collate.

    Yields per item:
        visual         [N, V]
        audio          [N, A]
        caption        [N, C]
        query          [Q]
        global_emb     [Q]
        gt_relevance   [N]
        gt_boundary    [2]   (normalized to [0,1] by video duration)
        num_shots      int
        video_id, query_text, recipe_type
    """

    def __init__(
        self,
        annotations: List[Dict],
        features_dir: str,
        query_cache_path: str,
        max_shots: int = 256,
        overlap_threshold: float = 0.5,
        require_features: bool = True,
        cache_features_in_ram: bool = False,
    ):
        self.features_dir = features_dir
        self.max_shots = max_shots
        self.overlap_threshold = overlap_threshold
        self.cache_features_in_ram = cache_features_in_ram
        self._ram_cache: Dict[str, ShotFeatures] = {}

        # Filter annotations to those whose feature .npz exists.
        self.annotations: List[Dict] = []
        missing = 0
        for r in annotations:
            if os.path.isfile(self._feature_path(r["video_id"])):
                self.annotations.append(r)
            else:
                missing += 1
        if missing > 0:
            msg = f"{missing}/{len(annotations)} YouCook2 annotations skipped — missing feature .npz"
            if require_features:
                log.warning(msg)
            else:
                log.info(msg)

        if not os.path.isfile(query_cache_path):
            raise FileNotFoundError(
                f"Query embedding cache not found: {query_cache_path}. "
                f"Run precompute_queries.py with the YouCook2 sentences first."
            )
        cache = np.load(query_cache_path, allow_pickle=True)
        self.query_to_emb: Dict[str, np.ndarray] = {
            str(k): v for k, v in zip(cache["queries"], cache["embeddings"])
        }
        log.info(
            f"YouCook2Dataset: {len(self.annotations)} examples, "
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
                f"YouCook2 query not in cache: '{query[:60]}...' "
                f"(rebuild query cache to include current splits)"
            )

        # Truncate to max_shots. YouCook2 videos are ~5 min, so at 2s windows that's
        # ~150 shots; max_shots default = 256 (enough headroom).
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
            "recipe_type": r.get("recipe_type", ""),
        }
