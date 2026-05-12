"""
InternVideo2 feature extractor — replaces the multi-stage CLIP+wav2vec2+Whisper path.

Produces .npz files in the existing `ShotFeatures` schema so the existing
`CharadesSTADataset` loader works unchanged. `audio_features` and
`caption_features` are zeroed — the QD-DETR head doesn't consume them, and the
unified-encoder hypothesis is that they're redundant. Re-fill them later (e.g.
subtitle tokens à la MiniGPT4-Video) if the ablation shows the unified encoder
underperforms the multi-modal baseline.

Output schema (.npz, same as feature_extractor.py):
    video_id, video_path, duration            (str, str, float)
    shot_boundaries     (N, 2)  float32 — uniform-window (start_sec, end_sec)
    visual_features     (N, D)  float32 — InternVideo2 vision-tower output
    audio_features      (N, 0)  float32 — empty placeholder (zero-width)
    caption_features    (N, 0)  float32 — empty placeholder
    asr_transcripts     (N,)    object   — empty strings
    global_metadata_emb (0,)    float32  — empty placeholder
    title, genre, synopsis, tone (str)

CLI (single video):
    python -m jockey.open_source.training.iv2_feature_extractor \\
        --video path/to/video.mp4 \\
        --out   features/iv2/myvideo.npz \\
        --window-sec 2.0 \\
        --frames-per-clip 4
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import List, Optional

import numpy as np

from jockey.open_source.indexer import extract_frames, _get_video_duration
from jockey.open_source.training.feature_extractor import ShotFeatures, uniform_windows
from jockey.open_source.training.iv2_encoder import InternVideo2Encoder

log = logging.getLogger(__name__)


class IV2FeatureExtractor:
    """Per-video extractor: uniform windows → IV2 vision features."""

    def __init__(
        self,
        model_name: str = "OpenGVLab/InternVideo2-Stage2_1B-224p-f4",
        device: str = "cuda",
        window_sec: float = 2.0,
        frames_per_clip: int = 4,
        image_size: int = 224,
        dtype: str = "fp16",
        encode_batch_size: int = 16,
    ):
        self.window_sec = window_sec
        self.frames_per_clip = frames_per_clip
        self.encode_batch_size = encode_batch_size
        self.encoder = InternVideo2Encoder(
            model_name_or_path=model_name,
            device=device,
            frames_per_clip=frames_per_clip,
            image_size=image_size,
            dtype=dtype,
        )

    def extract(
        self,
        video_path: str,
        video_id: Optional[str] = None,
        title: str = "",
        genre: str = "",
        synopsis: str = "",
        tone: str = "",
    ) -> ShotFeatures:
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        if video_id is None:
            video_id = os.path.splitext(os.path.basename(video_path))[0]

        t0 = time.time()
        duration = _get_video_duration(video_path)
        windows = uniform_windows(duration, self.window_sec)
        n = len(windows)
        log.info(
            f"[{video_id}] {duration:.1f}s → {n} windows × {self.window_sec:.1f}s "
            f"({self.frames_per_clip} frames/clip)"
        )

        # Extract frames for every window (CPU-side I/O; cheap relative to GPU)
        frame_batches: List[np.ndarray] = []
        for start, end in windows:
            frames = extract_frames(
                video_path, start, end, max_frames=self.frames_per_clip,
            )
            frame_batches.append(frames)

        # Encode in chunks to keep VRAM bounded on T4
        all_feats: List[np.ndarray] = []
        for i in range(0, n, self.encode_batch_size):
            chunk = frame_batches[i : i + self.encode_batch_size]
            feats = self.encoder.encode_video_batch(chunk)  # [B, D]
            all_feats.append(feats)
        visual = np.concatenate(all_feats, axis=0) if all_feats else (
            np.zeros((0, self.encoder.embedding_dim), dtype=np.float32)
        )

        # Empty placeholders for audio/caption/global (downstream IV2 head ignores them)
        audio = np.zeros((n, 0), dtype=np.float32)
        caption = np.zeros((n, 0), dtype=np.float32)
        global_emb = np.zeros((0,), dtype=np.float32)
        transcripts = [""] * n

        elapsed = time.time() - t0
        log.info(
            f"[{video_id}] extracted in {elapsed:.1f}s "
            f"({elapsed / max(n, 1):.2f}s/window, dim={visual.shape[1]})"
        )

        return ShotFeatures(
            video_id=video_id,
            video_path=os.path.abspath(video_path),
            duration=duration,
            shot_boundaries=np.array(windows, dtype=np.float32),
            visual_features=visual,
            audio_features=audio,
            caption_features=caption,
            asr_transcripts=transcripts,
            global_metadata_emb=global_emb,
            title=title,
            genre=genre,
            synopsis=synopsis,
            tone=tone,
        )


def extract_video(
    video_path: str,
    out_path: str,
    video_id: Optional[str] = None,
    window_sec: float = 2.0,
    frames_per_clip: int = 4,
    model_name: str = "OpenGVLab/InternVideo2-Stage2_1B-224p-f4",
    device: str = "cuda",
    dtype: str = "fp16",
    encode_batch_size: int = 16,
) -> ShotFeatures:
    extractor = IV2FeatureExtractor(
        model_name=model_name,
        device=device,
        window_sec=window_sec,
        frames_per_clip=frames_per_clip,
        dtype=dtype,
        encode_batch_size=encode_batch_size,
    )
    feats = extractor.extract(video_path, video_id=video_id)
    feats.save(out_path)
    log.info(f"Saved features ({feats.num_shots} windows) → {out_path}")
    return feats


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    p = argparse.ArgumentParser(
        description="Extract per-window InternVideo2 features for one video."
    )
    p.add_argument("--video", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--video-id", default=None)
    p.add_argument(
        "--window-sec",
        type=float, default=2.0,
        help="Window length in seconds. 1-2s typical for Charades-STA.",
    )
    p.add_argument(
        "--frames-per-clip",
        type=int, default=4,
        help="Frames sampled per window. InternVideo2-1B was trained with 4.",
    )
    p.add_argument(
        "--model",
        default="OpenGVLab/InternVideo2-Stage2_1B-224p-f4",
        help="HF repo for the InternVideo2 checkpoint.",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="fp16", choices=["fp16", "bf16", "fp32"])
    p.add_argument("--encode-batch-size", type=int, default=16)
    args = p.parse_args()

    extract_video(
        video_path=args.video,
        out_path=args.out,
        video_id=args.video_id,
        window_sec=args.window_sec,
        frames_per_clip=args.frames_per_clip,
        model_name=args.model,
        device=args.device,
        dtype=args.dtype,
        encode_batch_size=args.encode_batch_size,
    )


if __name__ == "__main__":
    main()
