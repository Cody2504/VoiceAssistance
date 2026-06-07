"""InternVideo2-1B single-video feature extractor (thesis / offline only).

Produces the per-clip visual feature tensor that the R2-adapter / CG-DETR head
trains on, in the SAME shape and on-disk layout SG-DETR's InterVidV2-1b
features use, so a head trained on our features and on SG-DETR's released
features are directly comparable.

Output: an ``.npz`` with
    visual_features : float16/float32  [n_clips, dim]   (dim = 512 for IV2-1b, CLIP-aligned)
    clip_length_sec : float scalar     (seconds covered per clip)
    fps_sampled     : float scalar     (frame sample rate used)
matching the key the colab notebook reads (``d["visual_features"]``).

ISOLATION: imports nothing from ``backend/`` / ``main.*``. Torch + the heavy
encoder are imported lazily so ``--help`` and the frame plumbing run without a
GPU. Following the repo's stated rule (encoders/config.py) we NEVER fall back
to random embeddings — if a real encoder can't be loaded we fail loudly.

ENCODER BACKENDS (``--backend`` / env ``IV2_BACKEND``):
  sgdetr  (recommended) — reuse SG-DETR's shipped InternVideo2-1b extractor.
            Set ``IV2_SGDETR_REPO=/path/to/ai-forever/sg-detr`` (the repo's
            ``features-extractor/`` dir). We import its encoder so our features
            are byte-compatible with the released ``iv2_1b_*`` features.
  hf      — OpenGVLab InternVideo2 stage-2 via its own package + checkpoint.
            Set ``IV2_HF_CKPT=/path/to/InternVideo2-stage2_1b-224p-f4.pt``.

Usage:
    python -m jockey.open_source.training.iv2_feature_extractor \
        --video /data/charades/3MSZA.mp4 --out features/iv2_charades/3MSZA.npz
"""
from __future__ import annotations

import argparse
import logging
import os
from typing import Protocol

import numpy as np

log = logging.getLogger("iv2.extract")

# IV2-1b clip-feature defaults. SG-DETR/lighthouse convention is 2-second clips
# over the whole video; the encoder consumes a small fixed stack of frames per
# clip. Keep these in sync with whatever the chosen backend was trained on.
DEFAULT_CLIP_LENGTH_SEC = 2.0
DEFAULT_FRAMES_PER_CLIP = 4          # IV2 stage2 1b-224p-f4 == 4 frames/clip
DEFAULT_INPUT_SIZE = 224
# SG-DETR's released "InterVidV2-1b" features are the CLIP-ALIGNED InternVideo2
# embedding (512-d), not the raw stage2 ViT width (768). Verified on the pod:
# the traced video_encoder.pt outputs 512-d. We don't hard-fail on a mismatch;
# the true dim is learned from the first encoded clip.
EXPECTED_DIM = 512


# --------------------------------------------------------------------------- #
# Encoder backend                                                             #
# --------------------------------------------------------------------------- #
class ClipEncoder(Protocol):
    """Encodes one clip's frame stack -> a single feature vector.

    frames: uint8 ndarray [T, H, W, 3].  returns: float ndarray [dim].
    """
    dim: int
    def encode_clip(self, frames: np.ndarray) -> np.ndarray: ...


def load_encoder(backend: str, device: str) -> ClipEncoder:
    backend = (backend or "").lower()
    if backend == "sgdetr":
        return _SGDetrEncoder(device)
    if backend == "hf":
        return _HFInternVideo2Encoder(device)
    raise SystemExit(
        f"Unknown --backend {backend!r}. Use 'sgdetr' (recommended) or 'hf'.\n"
        "Neither falls back to random features by design."
    )


class _SGDetrEncoder:
    """Runs SG-DETR's released InternVideo2-1b ("InterVidV2") video encoder so
    our features match the ``iv2_1b_*`` features the repo ships.

    The encoder is a TorchScript module (``torch.jit.load``) — the thing that
    determines feature compatibility. We replicate SG-DETR's *trivial* pre/post
    ops here (``VideoTransforms`` normalize + ``VideoInference``'s 4-frame
    select + renormalization) with their exact constants, instead of importing
    their ``src`` package. That import pulls ``src.inference.__init__`` →
    AudioExtractor → torchaudio/torchlibrosa/boto3, a fragile chain we don't
    need just to run the video tower. Math is byte-identical to theirs.

    Env:
      IV2_SGDETR_VIDEO_CKPT  path to the traced ``video_encoder.pt`` weights
                             (FE README Drive folder; download script `weights` mode)
    """

    dim = EXPECTED_DIM
    fnum = DEFAULT_FRAMES_PER_CLIP                            # frames the model consumes
    # src/datasets/transforms.py VideoTransforms defaults (applied to raw/255):
    _vt_mean = (0.485, 0.456, 0.406)
    _vt_std = (0.229, 0.224, 0.225)
    # src/inference/extraction/video_extractor.py VideoInference renorm consts:
    _imean, _istd = 0.45, 0.225
    _vmean = (0.485, 0.456, 0.406)
    _vstd = (0.229, 0.224, 0.225)

    def __init__(self, device: str) -> None:
        ckpt = os.environ.get("IV2_SGDETR_VIDEO_CKPT", "").strip()
        if not ckpt or not os.path.isfile(ckpt):
            raise SystemExit(
                "backend=sgdetr needs the traced video encoder weights.\n"
                "  ASSETS=weights bash download_sg_detr_assets.sh   # fetches video_encoder.pt\n"
                "  export IV2_SGDETR_VIDEO_CKPT=/abs/path/to/video_encoder.pt"
            )
        import torch
        self._torch = torch
        self.device = torch.device(device)
        try:
            self._model = torch.jit.load(ckpt, map_location=self.device).to(self.device).eval()
        except Exception as exc:
            raise SystemExit(
                f"torch.jit.load failed on {ckpt!r}: {exc}\n"
                "If this says 'not a ScriptModule', the download is a raw (non-traced) "
                "checkpoint — build the model from OpenGVLab's InternVideo2 repo instead."
            ) from exc
        # cached normalization tensors [1,C,1,1] for [T,C,H,W] frames
        v = lambda t: torch.tensor(t).view(1, -1, 1, 1)  # noqa: E731
        self._vt_m, self._vt_s = v(self._vt_mean), v(self._vt_std)

    def encode_clip(self, frames: np.ndarray) -> np.ndarray:
        """frames: uint8 [T, H, W, 3]  ->  float32 [dim]."""
        torch = self._torch
        with torch.no_grad():
            x = torch.from_numpy(frames).permute(0, 3, 1, 2).contiguous().float()  # [T,3,H,W]
            x = x.div(255.0).sub(self._vt_m).div(self._vt_s)        # VideoTransforms
            x = x.permute(1, 0, 2, 3).unsqueeze(0)                  # [1,C,T,H,W]
            x = self._select_frames(x)                              # T -> fnum (dim 2)
            x = x.mul(self._istd).add(self._imean)                  # denorm (imagenet)
            vm = torch.tensor(self._vmean).view(1, -1, 1, 1, 1)
            vs = torch.tensor(self._vstd).view(1, -1, 1, 1, 1)
            x = x.sub(vm).div(vs)                                   # renorm (viclip)
            emb = self._model(x.to(self.device)).float().cpu()
        vec = np.asarray(emb, dtype=np.float32).reshape(-1)
        if vec.shape[0] != self.dim:
            self.dim = vec.shape[0]
        return vec

    def _select_frames(self, batch):
        """Mirror VideoInference._extract_relevant_frames: pick fnum frames along T (dim 2)."""
        torch = self._torch
        t = batch.size(2)
        if t < self.fnum:
            raise ValueError(f"clip has {t} frames < fnum={self.fnum}")
        step = t // self.fnum
        idx = torch.arange(0, t, step)[: self.fnum]
        return torch.index_select(batch, 2, idx.to(batch.device))


class _HFInternVideo2Encoder:
    """OpenGVLab InternVideo2 stage-2 (1B) reference path. Requires the
    InternVideo2 package + checkpoint; verify the class/forward against your
    installed build — the API has shifted across releases."""

    dim = EXPECTED_DIM

    def __init__(self, device: str) -> None:
        ckpt = os.environ.get("IV2_HF_CKPT", "").strip()
        if not ckpt or not os.path.isfile(ckpt):
            raise SystemExit(
                "backend=hf needs IV2_HF_CKPT pointing at an InternVideo2 "
                "stage-2 1B checkpoint (e.g. InternVideo2-stage2_1b-224p-f4.pt)."
            )
        import torch  # lazy
        self._torch = torch
        self.device = device
        # NOTE: loading the IV2 stage2 ViT requires OpenGVLab's model code +
        # config. This is the one place to instantiate it; left as the explicit
        # integration seam rather than a guessed import that crashes opaquely.
        raise SystemExit(
            "backend=hf reference path is not wired to a specific InternVideo2 "
            "build. Recommended: use --backend sgdetr (their extractor) so "
            "features match the released iv2_1b_* set. If you must use HF, "
            "instantiate the stage2 ViT here and implement encode_clip()."
        )


# --------------------------------------------------------------------------- #
# Frame / clip plumbing (fully runnable, no model needed)                     #
# --------------------------------------------------------------------------- #
def read_clips(
    video_path: str,
    clip_length_sec: float,
    frames_per_clip: int,
    input_size: int,
) -> tuple[np.ndarray, float]:
    """Decode ``video_path`` into ``[n_clips, frames_per_clip, H, W, 3]`` uint8.

    Each clip spans ``clip_length_sec`` of wall-clock; within it we sample
    ``frames_per_clip`` evenly-spaced frames and center-crop/resize to
    ``input_size``. Returns (clips, true_fps).
    """
    # decord is fastest but has no py3.12 wheels on some setups; fall back to
    # OpenCV, which we already depend on for resize. Same sampling either way.
    try:
        from decord import VideoReader, cpu  # type: ignore
        vr = VideoReader(video_path, ctx=cpu(0))
        fps = float(vr.get_avg_fps()) or 30.0
        n_frames = len(vr)
        get_batch = lambda idxs: vr.get_batch(idxs).asnumpy()  # noqa: E731
        backend = "decord"
    except ImportError:
        get_batch, fps, n_frames = _cv2_reader(video_path)
        backend = "opencv"

    duration = n_frames / fps
    n_clips = max(1, int(duration // clip_length_sec))
    log.info("decode[%s]: %s  fps=%.2f frames=%d dur=%.1fs -> %d clips",
             backend, os.path.basename(video_path), fps, n_frames, duration, n_clips)

    clips = np.empty((n_clips, frames_per_clip, input_size, input_size, 3), dtype=np.uint8)
    for c in range(n_clips):
        t0, t1 = c * clip_length_sec, (c + 1) * clip_length_sec
        idxs = np.linspace(t0 * fps, min(t1 * fps, n_frames - 1),
                           frames_per_clip).astype(int).tolist()
        batch = get_batch(idxs)                             # [T, H, W, 3] uint8 RGB
        clips[c] = _resize_center_crop(batch, input_size)
    return clips, fps


def _cv2_reader(video_path: str):
    """OpenCV fallback: returns (get_batch(idxs)->[T,H,W,3] RGB uint8, fps, n_frames)."""
    import cv2  # type: ignore
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not open {video_path!r}")
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    def get_batch(idxs):
        out = []
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
            ok, frame = cap.read()
            if not ok or frame is None:
                if out:
                    out.append(out[-1])
                    continue
                raise SystemExit(f"OpenCV failed to read frame {i} of {video_path!r}")
            out.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return np.stack(out, axis=0)

    return get_batch, fps, n_frames


def _resize_center_crop(batch: np.ndarray, size: int) -> np.ndarray:
    """Resize shorter side to ``size`` then center-crop to size×size."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise SystemExit("opencv-python is required for resize: pip install opencv-python") from exc
    out = np.empty((batch.shape[0], size, size, 3), dtype=np.uint8)
    for i, frame in enumerate(batch):
        h, w = frame.shape[:2]
        scale = size / min(h, w)
        rw, rh = max(size, int(round(w * scale))), max(size, int(round(h * scale)))
        r = cv2.resize(frame, (rw, rh), interpolation=cv2.INTER_AREA)
        y0, x0 = (rh - size) // 2, (rw - size) // 2
        out[i] = r[y0:y0 + size, x0:x0 + size]
    return out


def extract(
    video_path: str,
    out_path: str,
    *,
    backend: str,
    device: str,
    clip_length_sec: float = DEFAULT_CLIP_LENGTH_SEC,
    frames_per_clip: int = DEFAULT_FRAMES_PER_CLIP,
    input_size: int = DEFAULT_INPUT_SIZE,
    skip_existing: bool = False,
) -> str | None:
    """Extract IV2 features for one video, save to ``out_path`` (.npz)."""
    if skip_existing and os.path.isfile(out_path):
        log.info("skip-existing: %s", out_path)
        return out_path

    clips, fps = read_clips(video_path, clip_length_sec, frames_per_clip, input_size)
    encoder = load_encoder(backend, device)            # fails loud if unavailable

    # Encode then stack — the true feature dim is whatever the encoder emits
    # (no pre-allocation that assumes a width).
    feats = np.stack([encoder.encode_clip(clips[i]) for i in range(clips.shape[0])], axis=0)
    feats = feats.astype(np.float32)

    if feats.shape[1] != EXPECTED_DIM:
        log.warning("encoder dim=%d != expected IV2-1b dim=%d", feats.shape[1], EXPECTED_DIM)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp.npz"
    np.savez_compressed(
        tmp,
        visual_features=feats.astype(np.float16),      # half-precision on disk
        clip_length_sec=np.float32(clip_length_sec),
        fps_sampled=np.float32(fps),
    )
    os.replace(tmp, out_path)
    log.info("saved %s  shape=%s", out_path, feats.shape)
    return out_path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="InternVideo2-1B single-video feature extractor")
    p.add_argument("--video", required=True, help="input video path")
    p.add_argument("--out", required=True, help="output .npz path")
    p.add_argument("--backend", default=os.environ.get("IV2_BACKEND", "sgdetr"),
                   choices=["sgdetr", "hf"], help="encoder backend")
    p.add_argument("--device", default=os.environ.get("IV2_DEVICE", "cuda"))
    p.add_argument("--clip-length-sec", type=float, default=DEFAULT_CLIP_LENGTH_SEC)
    p.add_argument("--frames-per-clip", type=int, default=DEFAULT_FRAMES_PER_CLIP)
    p.add_argument("--input-size", type=int, default=DEFAULT_INPUT_SIZE)
    p.add_argument("--skip-existing", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    a = _build_parser().parse_args(argv)
    extract(
        a.video, a.out,
        backend=a.backend, device=a.device,
        clip_length_sec=a.clip_length_sec, frames_per_clip=a.frames_per_clip,
        input_size=a.input_size, skip_existing=a.skip_existing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
