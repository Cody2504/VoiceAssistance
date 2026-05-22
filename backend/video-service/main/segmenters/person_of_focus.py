"""Cut 3 / Task 11.12 — person_of_focus.

Detects faces with InsightFace, embeds with ArcFace, clusters across shots,
and emits one segment per contiguous run where a given cluster is the focal
face. Heavy enough that we only run it in the vast.ai GPU image; on a laptop
without insightface installed the import-guard returns an empty track.
"""
from __future__ import annotations

import logging
import math
import os
import subprocess
import tempfile
from functools import lru_cache
from typing import Any
from uuid import UUID

from main.api.segments_types import SegmentDefinition
from main.models.video import Video

from .qdrant_io import read_shots
from .video_io import fetch_video, stream_url

log = logging.getLogger(__name__)


MIN_FACE_AREA_FRAC = 0.02


def _bbox_area(bbox: list[float]) -> float:
    if not bbox or len(bbox) < 4:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _pick_focal(faces: list[dict[str, Any]]) -> int | None:
    best: tuple[int, float] | None = None
    for f in faces:
        cid = f.get("cluster_id", -1)
        if cid is None or cid < 0:
            continue
        area = _bbox_area(f.get("bbox", []))
        if best is None or area > best[1]:
            best = (cid, area)
    return best[0] if best else None


def _segments_from_focal_sequence(
    shots: list[dict[str, Any]], focal_per_shot: list[int | None], field_names: set[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(shots):
        cid = focal_per_shot[i]
        if cid is None:
            i += 1
            continue
        j = i
        while j + 1 < len(shots) and focal_per_shot[j + 1] == cid:
            j += 1
        meta: dict[str, Any] = {}
        if "person_label" in field_names:
            meta["person_label"] = f"person_{cid}"
        if "screen_time_s" in field_names:
            meta["screen_time_s"] = round(
                sum(sh["t_end"] - sh["t_start"] for sh in shots[i : j + 1]), 2
            )
        if "role" in field_names:
            meta["role"] = "primary"
        out.append({"t_start": shots[i]["t_start"], "t_end": shots[j]["t_end"], "metadata": meta})
        i = j + 1
    return out


@lru_cache(maxsize=1)
def _analyzer():
    try:
        import insightface  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    log.info("person_of_focus: loading insightface buffalo_l")
    app = insightface.app.FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0; na = 0.0; nb = 0.0
    for x, y in zip(a, b):
        dot += x * y; na += x * x; nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _cluster(embeddings: list[list[float]], threshold: float = 0.55) -> list[int]:
    centroids: list[list[float]] = []
    sizes: list[int] = []
    out: list[int] = []
    sim_threshold = 1.0 - threshold
    for emb in embeddings:
        if not emb:
            out.append(-1)
            continue
        best_idx, best_sim = -1, -1.0
        for i, c in enumerate(centroids):
            s = _cosine(emb, c)
            if s > best_sim:
                best_sim = s
                best_idx = i
        if best_idx != -1 and best_sim >= sim_threshold:
            out.append(best_idx)
            n = sizes[best_idx]
            centroids[best_idx] = [(c * n + e) / (n + 1) for c, e in zip(centroids[best_idx], emb)]
            sizes[best_idx] = n + 1
        else:
            out.append(len(centroids))
            centroids.append(list(emb))
            sizes.append(1)
    return out


def _extract_frame(video_path: str, t: float) -> str | None:
    fd, png = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video_path,
             "-frames:v", "1", "-loglevel", "quiet", png],
            check=True,
        )
        return png
    except subprocess.CalledProcessError:
        try: os.remove(png)
        except OSError: pass
        return None


def segment(video_id: UUID, definition: SegmentDefinition) -> list[dict[str, Any]]:
    shots = read_shots(video_id, with_vectors=False)
    if not shots:
        return []

    app = _analyzer()
    if app is None:
        log.warning(
            "person_of_focus:insightface not installed in this image — empty track. "
            "Build with Dockerfile.gpu for the vast.ai deployment.",
        )
        return []

    video = fetch_video(video_id)
    if video is None:
        return []

    import cv2  # type: ignore
    import urllib.request

    url = stream_url(video, public=False)
    fd, video_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, video_path)

        per_frame_faces: list[list[dict[str, Any]]] = []
        flat_embs: list[list[float]] = []
        flat_index: list[tuple[int, int]] = []

        for fi, sh in enumerate(shots):
            png = _extract_frame(video_path, sh["t_start"])
            faces_here: list[dict[str, Any]] = []
            if png is not None:
                try:
                    img = cv2.imread(png)
                    if img is not None:
                        for face_i, det in enumerate(app.get(img) or []):
                            bbox = [float(x) for x in det.bbox.tolist()]
                            emb = (
                                [float(x) for x in det.normed_embedding.tolist()]
                                if hasattr(det, "normed_embedding") else []
                            )
                            faces_here.append({"bbox": bbox, "embedding": emb, "cluster_id": -1})
                            flat_embs.append(emb)
                            flat_index.append((fi, face_i))
                finally:
                    try: os.remove(png)
                    except OSError: pass
            per_frame_faces.append(faces_here)

        cluster_ids = _cluster(flat_embs)
        for (fi, face_i), cid in zip(flat_index, cluster_ids):
            per_frame_faces[fi][face_i]["cluster_id"] = cid

        focal_per_shot = [_pick_focal(faces) for faces in per_frame_faces]
        field_names = {f.name for f in definition.fields}
        return _segments_from_focal_sequence(shots, focal_per_shot, field_names)
    finally:
        try: os.remove(video_path)
        except OSError: pass
