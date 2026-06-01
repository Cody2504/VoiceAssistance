"""
Open-source pipeline for Jockey video agent.

MediaFM-inspired architecture replaces TwelveLabs APIs with:
- InternVideo2/ViCLIP (video embeddings, 768-dim)
- wav2vec2 (audio embeddings, 768-dim)
- OpenAI text-embedding-3-large (text embeddings, 3072-dim)
- ZipFormer-30M (ASR for transcript extraction)
- MediaFM Transformer Encoder (3 layers, 8 heads — shot contextualization)
- Qdrant (vector search)
- Qwen2-VL-7B (video Q&A / text generation)
"""
