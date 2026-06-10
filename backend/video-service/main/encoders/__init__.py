"""
Open-source encoder stack for the Jockey video agent (replaces TwelveLabs APIs):
- CLIP-L: openai/clip-vit-large-patch14, frame mean-pooled (visual, 768-d)
- ViCLIP (vendored InternVideo) — temporal motion retrieval (768-d, gated)
- OpenAI text-embedding-3-large via OpenRouter (text, 3072-d)
- Whisper (ASR), PANN CNN14 (audio tags), CLAP (text↔audio), easyocr (OCR)
- pyannote 3.1 (speaker diarization, gated)
- GroundingDINO (query-time open-vocab object verification, gated)
- Qwen3-VL via OpenRouter (captions, action re-captions, video Q&A)
- Qdrant (vector search)
"""
