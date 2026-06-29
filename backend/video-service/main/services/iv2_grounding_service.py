"""InternVideo2 + trained SG-DETR grounding service.

Grounds queries with the InternVideo2-1B towers (SG-DETR's released TorchScript
encoders) feeding the **trained SG-DETR head** (`MRDETR`, "Saliency Guided Hybrid
DETR", WACV 2026 — vendored under ``main.vendor.sgdetr``). Selected when
``settings.grounding_backend == "iv2"``; mirrors ``LighthouseService`` method
names so ``pipeline/ground_iv2.py`` + the Highlights tile can swap backends.

PIPELINE (validated end-to-end on a 3090):
  ingest:  video -> IV2 video encoder -> [n_clips, 512] features (cached to S3)
  query:   cached [n_clips,512] -> +2-d TEF -> [n,514] -> ≤76-clip windows
           -> MRDETR(src_vid, src_txt=IV2-text per-token) -> Preparator
           -> PostProcessorDETR -> moments (start,end,score) + per-clip saliency.

SELF-CONTAINED: no ``jockey`` / external ``sg-detr`` import. The frame reader is
vendored at ``main.encoders.iv2_video``; the model+postprocessor under
``main.vendor.sgdetr``. The head weights load from a pre-stripped pure state-dict
(``iv2_sgdetr_head_ckpt``) so unpickling needs no training-time modules.
"""
from __future__ import annotations

import logging
import os
import threading

import numpy as np

log = logging.getLogger(__name__)

# Matches the validated SG-DETR / InternVideo2-1b setup.
CLIP_LENGTH_SEC = 2.0
FRAMES_PER_CLIP = 4
INPUT_SIZE = 224
FEATURE_DIM = 512                       # IV2 video-encoder width (pre-TEF)
TEXT_MAX_LEN = 40                       # bert-large-uncased, per SG-DETR
MAX_VIDEO_CLIPS = 76                    # MRDETR max_video_length
WINDOW_CLIPS = 72                       # ≤76 and a multiple of 4 (FPN strides)
# VideoTransforms + VideoInference renorm constants (verbatim from sg-detr FE).
_VT_MEAN, _VT_STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
_IMEAN, _ISTD = 0.45, 0.225
_VMEAN, _VSTD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)

_CFG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vendor", "sgdetr", "configs"))

_LOCK = threading.Lock()
_INSTANCE: "IV2GroundingService | None" = None


def get_iv2_grounding() -> "IV2GroundingService":
    """Process-wide singleton wired to settings (real service path)."""
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                from main.settings import get_settings
                s = get_settings()
                _INSTANCE = IV2GroundingService(
                    video_ckpt=s.iv2_video_ckpt,
                    text_ckpt=s.iv2_text_ckpt,
                    head_ckpt=s.iv2_sgdetr_head_ckpt,
                    device=s.iv2_device,
                    clip_length_sec=s.iv2_clip_length_sec,
                )
    return _INSTANCE


class IV2GroundingService:
    """IV2 video+text encoders + trained SG-DETR (MRDETR) head.

    Constructor takes explicit ckpt paths (env fallback) so it is testable
    without the full settings / DB / MinIO stack. The video encoder is loaded
    lazily (only ingest needs it); the text encoder + head load eagerly since
    query-time grounding needs them.
    """

    def __init__(
        self,
        video_ckpt: str | None = None,
        text_ckpt: str | None = None,
        head_ckpt: str | None = None,
        device: str = "cuda",
        clip_length_sec: float = CLIP_LENGTH_SEC,
    ) -> None:
        import torch
        self._torch = torch
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.clip_length = clip_length_sec

        self._video_ckpt = video_ckpt or os.environ.get("IV2_SGDETR_VIDEO_CKPT", "")
        text_ckpt = text_ckpt or os.environ.get("IV2_SGDETR_TEXT_CKPT", "")
        head_ckpt = head_ckpt or os.environ.get("IV2_SGDETR_HEAD_CKPT", "")
        if not os.path.isfile(text_ckpt):
            raise RuntimeError(f"IV2 text_encoder not found: {text_ckpt!r}")
        if not os.path.isfile(head_ckpt):
            raise RuntimeError(f"SG-DETR head state-dict not found: {head_ckpt!r}")

        self._vt_m = torch.tensor(_VT_MEAN).view(1, -1, 1, 1)
        self._vt_s = torch.tensor(_VT_STD).view(1, -1, 1, 1)

        log.info("iv2:loading text=%s head=%s device=%s", text_ckpt, head_ckpt, self.device)
        self._tmodel = torch.jit.load(text_ckpt, map_location=self.device).to(self.device).eval()
        from transformers import BertTokenizer
        self._tok = BertTokenizer.from_pretrained("bert-large-uncased")
        self._vmodel = None  # lazy — only ingest's encode_video_to_features needs it
        self._build_head(head_ckpt)
        log.info("iv2:ready (head params=%d)", sum(p.numel() for p in self._head.parameters()))

    # head
    def _build_head(self, head_ckpt: str) -> None:
        """Instantiate MRDETR from the vendored config + load the stripped state-dict,
        plus the Preparator / PostProcessorDETR (also vendored, config-driven)."""
        from omegaconf import OmegaConf
        from hydra.utils import instantiate
        torch = self._torch

        base = OmegaConf.load(os.path.join(_CFG_DIR, "model_default.yaml"))
        root = OmegaConf.create({"model": base, "data": {"batch_size": 1}})
        head = instantiate(root.model.runner.model, _convert_="all").to(self.device).eval()
        # Pre-stripped pure state-dict (no training-time pickled modules).
        sd = torch.load(head_ckpt, map_location="cpu", weights_only=True)
        if isinstance(sd, dict) and "state_dict" in sd:  # tolerate a raw Lightning ckpt
            sd = {k[len("model."):]: v for k, v in sd["state_dict"].items() if k.startswith("model.")}
        res = head.load_state_dict(sd, strict=False)
        if res.missing_keys or res.unexpected_keys:
            log.warning("iv2:head load_state_dict missing=%d unexpected=%d",
                        len(res.missing_keys), len(res.unexpected_keys))
        self._head = head

        pp = OmegaConf.load(os.path.join(_CFG_DIR, "postprocessor_default.yaml"))
        self._preparator = instantiate(pp.preparator, _convert_="all")
        self._postproc = instantiate(pp.postprocessor, _convert_="all")

    # ingest
    @property
    def vmodel(self):
        """Lazy-load the 4 GB IV2 video encoder (ingest only)."""
        if self._vmodel is None:
            if not os.path.isfile(self._video_ckpt):
                raise RuntimeError(f"IV2 video_encoder not found: {self._video_ckpt!r}")
            log.info("iv2:loading video encoder %s", self._video_ckpt)
            self._vmodel = self._torch.jit.load(
                self._video_ckpt, map_location=self.device
            ).to(self.device).eval()
        return self._vmodel

    def encode_video_to_features(self, video_path: str) -> np.ndarray:
        """Whole video -> [n_clips, 512] features (no TEF). Cached at ingest."""
        from main.encoders.iv2_video import read_clips
        clips, _ = read_clips(video_path, self.clip_length, FRAMES_PER_CLIP, INPUT_SIZE)
        return np.stack([self._encode_clip(clips[i]) for i in range(clips.shape[0])], axis=0)

    def _encode_clip(self, frames: np.ndarray) -> np.ndarray:
        torch = self._torch
        with torch.no_grad():
            x = torch.from_numpy(frames).permute(0, 3, 1, 2).contiguous().float()
            x = x.div(255.0).sub(self._vt_m).div(self._vt_s)
            x = x.permute(1, 0, 2, 3).unsqueeze(0)             # [1,C,T,H,W]
            t = x.size(2); step = max(1, t // FRAMES_PER_CLIP)
            idx = torch.arange(0, t, step)[:FRAMES_PER_CLIP]
            x = torch.index_select(x, 2, idx.to(x.device))
            x = x.mul(_ISTD).add(_IMEAN)
            vm = torch.tensor(_VMEAN).view(1, -1, 1, 1, 1)
            vs = torch.tensor(_VSTD).view(1, -1, 1, 1, 1)
            x = x.sub(vm).div(vs)
            emb = self.vmodel(x.to(self.device)).float().cpu()
        return np.asarray(emb, dtype=np.float32).reshape(-1)

    # query
    def _embed_query_tokens(self, query: str):
        """Query -> (src_txt [1,L,512] per-token, src_txt_mask [1,L]).

        SG-DETR feeds the per-token text sequence (the 2nd encoder output,
        ``all_tfeat``) to MRDETR's cross-attention — NOT a pooled embedding.
        """
        torch = self._torch
        t = self._tok(query, padding="max_length", truncation=True,
                      max_length=TEXT_MAX_LEN, return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self._tmodel(t.input_ids, t.attention_mask)
        all_tfeat = out[1] if isinstance(out, (tuple, list)) else out
        return all_tfeat.float(), t.attention_mask.float()

    def predict_moments(
        self,
        query: str,
        features: np.ndarray,
        time_offset: float = 0.0,
        top_n: int = 10,
    ) -> list[tuple[float, float, float]]:
        """SG-DETR moment retrieval over cached IV2 features.

        Same contract as LighthouseService.predict_moments: list of
        (start_sec, end_sec, score) with ``time_offset`` applied.
        """
        if features is None or features.shape[0] == 0:
            return []
        src_txt, src_txt_mask = self._embed_query_tokens(query)
        moments: list[tuple[float, float, float]] = []
        for c0, c1, off in self._iter_windows(features.shape[0]):
            win = features[c0:c1]
            mw, _sal = self._run_head(src_txt, src_txt_mask, win, query)
            base = time_offset + off
            moments.extend((base + s, base + e, sc) for s, e, sc in mw)
        moments = _nms_1d(moments, iou_thr=0.7)
        moments.sort(key=lambda m: -m[2])
        return moments[:top_n]

    def predict_saliency(
        self,
        features: np.ndarray,
        query: str | None = None,
        time_offset: float = 0.0,
    ) -> list[tuple[float, float, float]]:
        """Per-clip saliency (start, end, score). Generic highlight query if none."""
        if features is None or features.shape[0] == 0:
            return []
        q = query or "an interesting key moment or highlight from the video"
        src_txt, src_txt_mask = self._embed_query_tokens(q)
        n = features.shape[0]
        agg = np.full(n, -np.inf, dtype=np.float32)
        for c0, c1, _off in self._iter_windows(n):
            win = features[c0:c1]
            _mw, sal = self._run_head(src_txt, src_txt_mask, win, q)
            m = min(len(sal), c1 - c0)
            agg[c0:c0 + m] = np.maximum(agg[c0:c0 + m], np.asarray(sal[:m], dtype=np.float32))
        agg[~np.isfinite(agg)] = float(np.nanmin(agg[np.isfinite(agg)])) if np.isfinite(agg).any() else 0.0
        return [
            (time_offset + i * self.clip_length, time_offset + (i + 1) * self.clip_length, float(agg[i]))
            for i in range(n)
        ]

    # helpers
    def _iter_windows(self, n_clips: int) -> list[tuple[int, int, float]]:
        """Non-overlapping ≤WINDOW_CLIPS windows: (clip_start, clip_end, offset_sec)."""
        out: list[tuple[int, int, float]] = []
        i = 0
        while i < n_clips:
            end = min(i + WINDOW_CLIPS, n_clips)
            out.append((i, end, i * self.clip_length))
            i = end
        return out

    def _run_head(self, src_txt, src_txt_mask, win_feats: np.ndarray, query: str):
        """Run MRDETR + postproc on one window of [Lw,512] features.

        Returns (moments [(start,end,score) in window-relative secs], saliency [Lw]).
        """
        torch = self._torch
        lw = win_feats.shape[0]
        feats = torch.from_numpy(np.ascontiguousarray(win_feats)).float()
        # +2-d TEF over the real window length
        tef_st = torch.arange(0, lw, 1.0) / max(lw, 1)
        tef = torch.stack([tef_st, tef_st + 1.0 / max(lw, 1)], dim=1)
        feats = torch.cat([feats, tef], dim=1)                 # [Lw, 514]
        # FPN padding -> multiple of 4
        pad = (-lw) % 4
        if pad:
            feats = torch.cat([feats, torch.zeros(pad, feats.shape[1])], dim=0)
        lp = feats.shape[0]
        src_vid = feats.unsqueeze(0).to(self.device)
        mask = torch.zeros(1, lp, device=self.device)
        mask[0, :lw] = 1.0
        duration = lw * self.clip_length
        meta = [{"qid": 0, "query": query, "vid": "v", "duration": duration}]
        batch = {
            "src_txt": src_txt, "src_txt_mask": src_txt_mask,
            "src_vid": src_vid, "src_vid_mask": mask, "vid": ["v"],
        }
        with torch.no_grad():
            outputs = self._head(**batch, meta=meta)
        _aux, detr = self._preparator(meta, batch, outputs)
        processed = self._postproc(detr)
        mw = processed[0]["pred_relevant_windows"]
        moments = [(float(r[0]), float(r[1]), float(r[2])) for r in mw.tolist()]
        sal = torch.as_tensor(detr[0]["pred_saliency_scores"]).float().cpu().numpy()
        return moments, sal


def _iou_1d(a, b) -> float:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def _nms_1d(moments: list[tuple[float, float, float]], iou_thr: float = 0.7):
    """Greedy 1-D NMS across windows (the per-window postproc already NMS'd)."""
    kept: list[tuple[float, float, float]] = []
    for m in sorted(moments, key=lambda x: -x[2]):
        if all(_iou_1d(m, k) < iou_thr for k in kept):
            kept.append(m)
    return kept
