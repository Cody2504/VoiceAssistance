"""Vendored real ViCLIP (research item A) — temporal video-text retrieval.

Source: OpenGVLab/InternVideo @ main, `Data/InternVid/viclip/` (Apache-2.0).
Files vendored verbatim: viclip.py, viclip_vision.py, viclip_text.py,
simple_tokenizer.py, bpe_simple_vocab_16e6.txt.gz — except ONE local change:
viclip.py's torch.load gets weights_only=False (the official ckpt pickles an
EasyDict that torch>=2.6 rejects by default). The upstream __init__'s
cv2-based helpers (frames2tensor etc.) are NOT vendored — preprocessing lives
in `main.encoders.motion_encoder`, which also keeps heavy imports lazy.

Weights: `ViClip-InternVid-10M-FLT.pth` (HF OpenGVLab/ViCLIP) at
`settings.motion_weights`. Runtime deps: torch, einops, timm, ftfy, regex, cv2.
"""
