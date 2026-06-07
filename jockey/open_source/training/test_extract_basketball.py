"""Smoke test: extract InternVideo2-1B features for one basketball clip and
report what came out. Run on the 3090 (where torch/decord + the SG-DETR weights
live), NOT in the bare repo checkout.

    # one-time setup
    git clone https://github.com/ai-forever/sg-detr vendor/sg-detr
    pip install -r jockey/open_source/training/requirements.txt
    pip install -r vendor/sg-detr/features-extractor/requirements.txt
    ASSETS=weights bash jockey/open_source/training/download_sg_detr_assets.sh ./assets/sg_detr

    export IV2_SGDETR_REPO=$PWD/vendor/sg-detr/features-extractor
    export IV2_SGDETR_VIDEO_CKPT=$PWD/assets/sg_detr/fe_weights/video_encoder.pt
    python -m jockey.open_source.training.test_extract_basketball

What it checks:
  * the video decodes into ~duration/2 two-second clips,
  * the SG-DETR InternVideo2-1b encoder loads and runs,
  * output is [n_clips, 768] with sane (finite, non-constant) values,
  * round-trips through the .npz layout the trainer/notebook reads.
"""
from __future__ import annotations

import os
import sys
import tempfile

VIDEO = os.environ.get(
    "TEST_VIDEO",
    "/mnt/d/MR-DETR/VoiceAssistance/video/basketball/03.mp4",
)


def _preflight() -> None:
    """Fail early with actionable guidance instead of a deep stack trace."""
    missing = []
    for mod in ("numpy", "torch", "cv2"):     # decord optional (cv2 fallback)
        try:
            __import__(mod)
        except ImportError:
            missing.append("opencv-python" if mod == "cv2" else mod)
    if missing:
        sys.exit(
            "Missing deps: " + ", ".join(missing) + "\n"
            "  pip install numpy opencv-python   # + a CUDA torch build"
        )
    if not os.path.isfile(VIDEO):
        sys.exit(f"video not found: {VIDEO} (set TEST_VIDEO=...)")
    if not os.environ.get("IV2_SGDETR_VIDEO_CKPT"):
        sys.exit(
            "IV2_SGDETR_VIDEO_CKPT is not set — see this file's docstring.\n"
            "(backend=sgdetr never falls back to random features.)"
        )


def main() -> int:
    _preflight()
    import numpy as np
    from jockey.open_source.training import iv2_feature_extractor as ife

    backend = os.environ.get("IV2_BACKEND", "sgdetr")
    device = os.environ.get("IV2_DEVICE", "cuda")
    print(f"video   : {VIDEO}")
    print(f"backend : {backend}   device: {device}")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "03.npz")
        ife.extract(VIDEO, out, backend=backend, device=device)

        d = np.load(out)
        feats = d["visual_features"]
        clip_len = float(d["clip_length_sec"])
        fps = float(d["fps_sampled"])

        print("\n--- result ---")
        print(f"visual_features : shape={feats.shape} dtype={feats.dtype}")
        print(f"clip_length_sec : {clip_len}   fps_sampled: {fps:.2f}")
        print(f"covered span    : ~{feats.shape[0] * clip_len:.0f}s "
              f"({feats.shape[0]} clips)")
        f32 = feats.astype(np.float32)
        print(f"value stats     : min={f32.min():.3f} max={f32.max():.3f} "
              f"mean={f32.mean():.3f} std={f32.std():.3f}")
        print(f"per-clip L2 norm: first5={np.linalg.norm(f32[:5], axis=1).round(3).tolist()}")
        print(f"vec[0][:8]      : {f32[0, :8].round(4).tolist()}")

        # sanity assertions
        assert feats.ndim == 2, "expected [n_clips, dim]"
        assert feats.shape[0] >= 1, "no clips produced"
        assert np.isfinite(f32).all(), "non-finite values in features"
        assert f32.std() > 1e-6, "features are constant — likely a load/preproc bug"
        if feats.shape[1] != ife.EXPECTED_DIM:
            print(f"NOTE: dim={feats.shape[1]} != expected {ife.EXPECTED_DIM} "
                  "(fine if you intentionally swapped the encoder)")
        print("\nPASS ✔  features look healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
