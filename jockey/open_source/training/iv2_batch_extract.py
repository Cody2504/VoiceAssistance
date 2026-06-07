"""Batch InternVideo2-1B feature extraction over a directory of videos.

Wraps :mod:`iv2_feature_extractor` for a whole dataset. Resumable via
``--skip-existing`` (re-run after a disconnect and it only does what's missing),
matching the colab notebook's Step 7 contract:

    python -m jockey.open_source.training.iv2_batch_extract \
        --videos-dir /data/charades --out-dir features/iv2_charades \
        --skip-existing

Loads the heavy encoder ONCE and reuses it across all videos (the single-video
CLI reloads per call — fine for smoke tests, wasteful for a full set).

ISOLATION: pure thesis tooling; imports nothing from ``backend/``.
"""
from __future__ import annotations

import argparse
import logging
import os

from jockey.open_source.training import iv2_feature_extractor as ife

log = logging.getLogger("iv2.batch")

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v")


def find_videos(videos_dir: str) -> list[str]:
    out: list[str] = []
    for root, _, files in os.walk(videos_dir):
        for f in sorted(files):
            if f.lower().endswith(VIDEO_EXTS):
                out.append(os.path.join(root, f))
    return out


def run(
    videos_dir: str,
    out_dir: str,
    *,
    backend: str,
    device: str,
    clip_length_sec: float = ife.DEFAULT_CLIP_LENGTH_SEC,
    frames_per_clip: int = ife.DEFAULT_FRAMES_PER_CLIP,
    input_size: int = ife.DEFAULT_INPUT_SIZE,
    skip_existing: bool = True,
    limit: int | None = None,
) -> dict:
    videos = find_videos(videos_dir)
    if limit:
        videos = videos[:limit]
    if not videos:
        raise SystemExit(f"no videos found under {videos_dir!r} (exts: {VIDEO_EXTS})")
    os.makedirs(out_dir, exist_ok=True)
    log.info("batch: %d videos  backend=%s device=%s -> %s",
             len(videos), backend, device, out_dir)

    # Load the encoder once and reuse it across videos.
    encoder = ife.load_encoder(backend, device)

    done, skipped, failed = 0, 0, 0
    for i, vpath in enumerate(videos, 1):
        vid = os.path.splitext(os.path.basename(vpath))[0]
        out_path = os.path.join(out_dir, f"{vid}.npz")
        if skip_existing and os.path.isfile(out_path):
            skipped += 1
            continue
        try:
            clips, fps = ife.read_clips(vpath, clip_length_sec, frames_per_clip, input_size)
            import numpy as np
            feats = np.stack(
                [encoder.encode_clip(clips[c]) for c in range(clips.shape[0])], axis=0
            ).astype(np.float32)
            tmp = out_path + ".tmp.npz"
            np.savez_compressed(
                tmp,
                visual_features=feats.astype(np.float16),
                clip_length_sec=np.float32(clip_length_sec),
                fps_sampled=np.float32(fps),
            )
            os.replace(tmp, out_path)
            done += 1
            log.info("[%d/%d] %s  shape=%s", i, len(videos), vid, feats.shape)
        except SystemExit:
            raise                       # config/availability errors should stop the run
        except Exception:
            failed += 1
            log.exception("[%d/%d] FAILED %s", i, len(videos), vid)

    summary = {"total": len(videos), "extracted": done, "skipped": skipped, "failed": failed}
    log.info("batch done: %s", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch InternVideo2-1B feature extraction")
    p.add_argument("--videos-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--backend", default=os.environ.get("IV2_BACKEND", "sgdetr"),
                   choices=["sgdetr", "hf"])
    p.add_argument("--device", default=os.environ.get("IV2_DEVICE", "cuda"))
    p.add_argument("--clip-length-sec", type=float, default=ife.DEFAULT_CLIP_LENGTH_SEC)
    p.add_argument("--frames-per-clip", type=int, default=ife.DEFAULT_FRAMES_PER_CLIP)
    p.add_argument("--input-size", type=int, default=ife.DEFAULT_INPUT_SIZE)
    p.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    p.add_argument("--limit", type=int, default=None, help="cap #videos (smoke test)")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    a = _build_parser().parse_args(argv)
    run(
        a.videos_dir, a.out_dir,
        backend=a.backend, device=a.device,
        clip_length_sec=a.clip_length_sec, frames_per_clip=a.frames_per_clip,
        input_size=a.input_size, skip_existing=a.skip_existing, limit=a.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
