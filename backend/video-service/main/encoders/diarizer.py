"""Speaker diarization (research item F) — pyannote speaker turns surfaced as
the `speakers` timeline track.

Runs `pyannote/speaker-diarization-3.1` (gated on HF — needs HF_TOKEN with the
model terms accepted) over the full audio once at ingest. Turns are normalized
(same-speaker merge, micro-turn drop) and stored on
`IngestArtifacts.speaker_turns`; `gen_speakers` turns them into timeline events
labeled with the overlapping transcript snippet, so "who said X, when" is a
free text search over the existing event fan-out stream.

Public API:
    d = SpeakerDiarizer.from_config(config, settings)
    if d.is_available():
        turns = d.diarize(local_path)
        # -> [{"t_start": 12.3, "t_end": 18.9, "speaker": "SPEAKER_00"}, ...]
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"


def normalize_turns(
    turns: list[dict],
    *,
    gap_tolerance: float = 1.0,
    min_duration: float = 0.5,
) -> list[dict]:
    """Sort by start, merge adjacent same-speaker turns (gap ≤ gap_tolerance),
    then drop micro-turns shorter than min_duration. Never raises."""
    cleaned = [
        t for t in turns
        if t.get("speaker") and t.get("t_start") is not None and t.get("t_end") is not None
    ]
    cleaned.sort(key=lambda t: float(t["t_start"]))
    merged: list[dict] = []
    for t in cleaned:
        t0, t1, spk = float(t["t_start"]), float(t["t_end"]), str(t["speaker"])
        if merged and merged[-1]["speaker"] == spk and t0 <= merged[-1]["t_end"] + gap_tolerance:
            merged[-1]["t_end"] = max(merged[-1]["t_end"], t1)
        else:
            merged.append({"t_start": t0, "t_end": t1, "speaker": spk})
    return [
        {"t_start": round(t["t_start"], 2), "t_end": round(t["t_end"], 2), "speaker": t["speaker"]}
        for t in merged
        if t["t_end"] - t["t_start"] >= min_duration
    ]


class SpeakerDiarizer:
    """pyannote 3.1 diarization pipeline behind the standard lazy/_UNAVAILABLE gate."""

    def __init__(self, model: str, hf_token: str):
        self.model = model
        self.hf_token = hf_token
        self._pipeline = None

    @classmethod
    def from_config(cls, config, settings) -> "SpeakerDiarizer":
        return cls(model=settings.diarization_model, hf_token=config.hf_token)

    def _lazy_load(self) -> None:
        if self._pipeline is not None:
            return
        if not self.hf_token:
            log.warning("SpeakerDiarizer unavailable: HF_TOKEN not set (model is gated)")
            self._pipeline = _UNAVAILABLE
            return
        try:
            import torch
            from pyannote.audio import Pipeline
            try:
                # pyannote.audio >= 4 renamed use_auth_token -> token
                pipe = Pipeline.from_pretrained(self.model, token=self.hf_token)
            except TypeError:
                pipe = Pipeline.from_pretrained(self.model, use_auth_token=self.hf_token)
            if pipe is None:
                raise RuntimeError(f"Pipeline.from_pretrained({self.model!r}) returned None "
                                   "(gated-model terms not accepted?)")
            if torch.cuda.is_available():
                pipe.to(torch.device("cuda"))
            self._pipeline = pipe
            log.info("SpeakerDiarizer ready (model=%s)", self.model)
        except Exception as exc:  # noqa: BLE001
            log.warning("SpeakerDiarizer unavailable: %s", exc)
            self._pipeline = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._pipeline not in (None, _UNAVAILABLE)

    def diarize(self, local_path: str) -> list[dict] | None:
        """Full-file diarization → normalized speaker turns in absolute video
        time. Best-effort: returns None on any failure."""
        self._lazy_load()
        if self._pipeline in (None, _UNAVAILABLE):
            return None
        try:
            import torch
            from main.encoders.audio_event_encoder import _load_full_audio_32k_mono
            samples = _load_full_audio_32k_mono(local_path)
            if samples is None or samples.size == 0:
                return None
            waveform = torch.from_numpy(samples).float().unsqueeze(0)  # [1, n]
            annotation = self._pipeline({"waveform": waveform, "sample_rate": 32000})
            # pyannote >= 4 wraps the Annotation in a DiarizeOutput
            if not hasattr(annotation, "itertracks"):
                annotation = annotation.speaker_diarization
            turns = [
                {"t_start": float(seg.start), "t_end": float(seg.end), "speaker": str(label)}
                for seg, _, label in annotation.itertracks(yield_label=True)
            ]
            return normalize_turns(turns)
        except Exception as exc:  # noqa: BLE001
            log.warning("SpeakerDiarizer: diarization failed for %s: %s", local_path, exc)
            return None
