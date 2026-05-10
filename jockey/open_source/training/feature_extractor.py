"""
Offline Feature Extractor — produces per-shot frozen features for training and indexing.

Wraps the existing pipeline encoders (ViCLIP/CLIP-L, wav2vec2, ZipFormer ASR, OpenAI
text embedding) to extract per-shot multimodal features from a video and save them
to a single .npz file.

Output schema (.npz):
    video_id            (str)
    video_path          (str)
    duration            (float)
    shot_boundaries     (N, 2)  float32  — (start_sec, end_sec) per shot
    visual_features     (N, 768)  float32 — frozen ViCLIP/CLIP-L per-shot embedding
    audio_features      (N, 768)  float32 — frozen wav2vec2 per-shot embedding
    caption_features    (N, 3072) float32 — text-emb-3-large of ASR transcript
    asr_transcripts     (N,)     object   — list of strings
    global_metadata_emb (3072,)  float32  — text-emb of (title, genre, synopsis, tone)
    title, genre, synopsis, tone (str)

CLI:
    python -m jockey.open_source.training.feature_extractor \\
        --video path/to/video.mp4 \\
        --out  features/myvideo.npz \\
        --title "My Video"

This is the offline foundation for the trained grounding head and for online indexing.
The encoders stay frozen — this module does no training.
"""
import argparse
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from jockey.open_source.config import config as default_config, PipelineConfig
from jockey.open_source.indexer import detect_shots, extract_frames, _get_video_duration

log = logging.getLogger(__name__)


@dataclass
class ShotFeatures:
    """Container for one video's per-shot multimodal features."""

    video_id: str
    video_path: str
    duration: float
    shot_boundaries: np.ndarray       # [N, 2]
    visual_features: np.ndarray       # [N, visual_dim]
    audio_features: np.ndarray        # [N, audio_dim]
    caption_features: np.ndarray      # [N, text_dim]
    asr_transcripts: List[str]
    global_metadata_emb: np.ndarray   # [text_dim]
    title: str = ""
    genre: str = ""
    synopsis: str = ""
    tone: str = ""

    @property
    def num_shots(self) -> int:
        return int(self.shot_boundaries.shape[0])

    def save(self, out_path: str) -> None:
        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        np.savez_compressed(
            out_path,
            video_id=self.video_id,
            video_path=self.video_path,
            duration=np.float32(self.duration),
            shot_boundaries=self.shot_boundaries.astype(np.float32),
            visual_features=self.visual_features.astype(np.float32),
            audio_features=self.audio_features.astype(np.float32),
            caption_features=self.caption_features.astype(np.float32),
            asr_transcripts=np.array(self.asr_transcripts, dtype=object),
            global_metadata_emb=self.global_metadata_emb.astype(np.float32),
            title=self.title,
            genre=self.genre,
            synopsis=self.synopsis,
            tone=self.tone,
        )

    @classmethod
    def load(cls, path: str) -> "ShotFeatures":
        data = np.load(path, allow_pickle=True)
        return cls(
            video_id=str(data["video_id"]),
            video_path=str(data["video_path"]),
            duration=float(data["duration"]),
            shot_boundaries=data["shot_boundaries"],
            visual_features=data["visual_features"],
            audio_features=data["audio_features"],
            caption_features=data["caption_features"],
            asr_transcripts=[str(s) for s in data["asr_transcripts"]],
            global_metadata_emb=data["global_metadata_emb"],
            title=str(data["title"]) if "title" in data.files else "",
            genre=str(data["genre"]) if "genre" in data.files else "",
            synopsis=str(data["synopsis"]) if "synopsis" in data.files else "",
            tone=str(data["tone"]) if "tone" in data.files else "",
        )


class FeatureExtractor:
    """Lazy-loaded multimodal feature extractor.

    Wraps the existing encoders (`ViCLIPEmbedder`, `AudioEncoder`, `ASREngine`,
    `TextEmbedder`, `MetadataEncoder`) and orchestrates per-shot encoding.

    All encoders are frozen — this module does no training.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        skip_audio: bool = False,
        skip_asr: bool = False,
        skip_metadata: bool = False,
    ):
        self.config = config or default_config
        self.skip_audio = skip_audio
        self.skip_asr = skip_asr
        self.skip_metadata = skip_metadata

        self._viclip = None
        self._audio_enc = None
        self._asr = None
        self._text_emb = None
        self._meta_enc = None

    # --- lazy loaders (encoders are heavy; only load what we need) ---

    def _load_viclip(self):
        if self._viclip is None:
            from jockey.open_source.viclip_embedder import ViCLIPEmbedder
            self._viclip = ViCLIPEmbedder(
                model_name_or_path=self.config.viclip_model_name,
                device=self.config.viclip_device,
            )
        return self._viclip

    def _load_audio(self):
        if self.skip_audio:
            return None
        if self._audio_enc is None:
            from jockey.open_source.audio_encoder import AudioEncoder
            self._audio_enc = AudioEncoder(
                model_name=self.config.audio_encoder_model,
                device=self.config.audio_encoder_device,
            )
        return self._audio_enc

    def _load_asr(self):
        if self.skip_asr:
            return None
        if self._asr is None:
            from jockey.open_source.asr import ASREngine
            self._asr = ASREngine(model_dir=self.config.zipformer_model_dir)
        return self._asr

    def _load_text_emb(self):
        if self._text_emb is None:
            from jockey.open_source.search import TextEmbedder
            self._text_emb = TextEmbedder(
                api_key=self.config.openrouter_api_key,
                model=self.config.text_embedding_model,
                base_url=self.config.openrouter_base_url,
            )
        return self._text_emb

    def _load_metadata(self):
        if self.skip_metadata:
            return None
        if self._meta_enc is None:
            from jockey.open_source.metadata_encoder import MetadataEncoder
            self._meta_enc = MetadataEncoder(text_embedder=self._load_text_emb())
        return self._meta_enc

    # --- main entry point ---

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
            raise FileNotFoundError(f"Video not found: {video_path}")

        if video_id is None:
            video_id = os.path.splitext(os.path.basename(video_path))[0]

        log.info(f"Extracting features: {video_path} (video_id={video_id})")
        t0 = time.time()

        duration = _get_video_duration(video_path)
        shots = detect_shots(video_path, threshold=self.config.shot_detection_threshold)
        n = len(shots)
        log.info(f"  Detected {n} shots (duration {duration:.1f}s)")

        # Allocate output buffers
        v_dim = self.config.viclip_embedding_dim
        a_dim = self.config.audio_embedding_dim
        t_dim = self.config.text_embedding_dim

        shot_boundaries = np.array(shots, dtype=np.float32)
        visual_feats = np.zeros((n, v_dim), dtype=np.float32)
        audio_feats = np.zeros((n, a_dim), dtype=np.float32)
        caption_feats = np.zeros((n, t_dim), dtype=np.float32)
        asr_transcripts: List[str] = []

        viclip = self._load_viclip()
        audio_enc = self._load_audio()
        asr = self._load_asr()
        text_emb = self._load_text_emb()

        for i, (start, end) in enumerate(shots):
            # Visual
            frames = extract_frames(
                video_path, start, end, max_frames=self.config.max_frames_per_shot
            )
            visual_feats[i] = viclip.encode_video(frames)

            # Audio
            if audio_enc is not None:
                try:
                    audio_feats[i] = audio_enc.encode_audio(
                        video_path, start_sec=start, end_sec=end
                    )
                except Exception as e:
                    log.warning(f"  shot {i}: audio encode failed: {e}")

            # ASR
            transcript = ""
            if asr is not None:
                try:
                    transcript = asr.transcribe(
                        video_path, start_sec=start, end_sec=end
                    ) or ""
                except Exception as e:
                    log.warning(f"  shot {i}: ASR failed: {e}")
            asr_transcripts.append(transcript)

            # Caption text embedding (uses ASR text; falls back to title placeholder)
            text_to_embed = transcript if transcript else f"{title or video_id} shot {i}"
            try:
                caption_feats[i] = text_emb.encode(text_to_embed)
            except Exception as e:
                log.warning(f"  shot {i}: caption emb failed: {e}")

            asr_preview = f" asr='{transcript[:40]}...'" if transcript else ""
            log.info(f"  shot {i:3d}: [{start:7.2f}-{end:7.2f}s]{asr_preview}")

        # Global metadata embedding
        global_emb = np.zeros(t_dim, dtype=np.float32)
        meta_enc = self._load_metadata()
        if meta_enc is not None and any([title, genre, synopsis, tone]):
            try:
                global_emb = meta_enc.encode(
                    title=title or video_id,
                    genre=genre,
                    synopsis=synopsis,
                    tone=tone,
                ).astype(np.float32)
            except Exception as e:
                log.warning(f"  global metadata emb failed: {e}")

        elapsed = time.time() - t0
        log.info(
            f"Extracted {n} shots in {elapsed:.1f}s "
            f"({elapsed / max(n, 1):.2f}s/shot)"
        )

        return ShotFeatures(
            video_id=video_id,
            video_path=os.path.abspath(video_path),
            duration=duration,
            shot_boundaries=shot_boundaries,
            visual_features=visual_feats,
            audio_features=audio_feats,
            caption_features=caption_feats,
            asr_transcripts=asr_transcripts,
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
    title: str = "",
    genre: str = "",
    synopsis: str = "",
    tone: str = "",
    skip_audio: bool = False,
    skip_asr: bool = False,
    skip_metadata: bool = False,
    config: Optional[PipelineConfig] = None,
) -> ShotFeatures:
    """Extract features from one video and save to disk. Convenience wrapper."""
    extractor = FeatureExtractor(
        config=config,
        skip_audio=skip_audio,
        skip_asr=skip_asr,
        skip_metadata=skip_metadata,
    )
    feats = extractor.extract(
        video_path,
        video_id=video_id,
        title=title,
        genre=genre,
        synopsis=synopsis,
        tone=tone,
    )
    feats.save(out_path)
    log.info(f"Saved features ({feats.num_shots} shots) → {out_path}")
    return feats


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Extract per-shot multimodal features from a video to a .npz file."
    )
    parser.add_argument("--video", required=True, help="Input video file")
    parser.add_argument("--out", required=True, help="Output .npz path")
    parser.add_argument("--video-id", default=None, help="Optional video ID (defaults to filename)")
    parser.add_argument("--title", default="", help="Video title (for [GLOBAL] token)")
    parser.add_argument("--genre", default="")
    parser.add_argument("--synopsis", default="")
    parser.add_argument("--tone", default="")
    parser.add_argument("--skip-audio", action="store_true", help="Skip audio (use zeros)")
    parser.add_argument("--skip-asr", action="store_true", help="Skip ASR (empty transcripts)")
    parser.add_argument("--skip-metadata", action="store_true", help="Skip [GLOBAL] metadata emb")
    args = parser.parse_args()

    feats = extract_video(
        video_path=args.video,
        out_path=args.out,
        video_id=args.video_id,
        title=args.title,
        genre=args.genre,
        synopsis=args.synopsis,
        tone=args.tone,
        skip_audio=args.skip_audio,
        skip_asr=args.skip_asr,
        skip_metadata=args.skip_metadata,
    )
    print(
        f"Saved {feats.num_shots} shots ({feats.duration:.1f}s) → {args.out}"
    )


if __name__ == "__main__":
    main()
