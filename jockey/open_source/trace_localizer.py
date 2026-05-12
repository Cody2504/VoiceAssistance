"""
TRACE Localizer — runtime wrapper for `Yongxin-Guo/trace-uni` (or sibling
checkpoints) used as the `find_moment` grounding backend.

TRACE is a video-LLM that emits interleaved (timestamp, score, caption) token
streams. For moment-retrieval queries we read the first event's start/end
timestamps. Charades-STA zero-shot R@1@IoU=0.5 = 43.7 per the paper.

## Install requirements

TRACE ships a custom `TraceMistralForCausalLM` model_type that is NOT in stock
transformers — `AutoModel.from_pretrained` alone will not work. You must clone
the TRACE GitHub repo and make its `trace.*` package importable:

    cd /content                       # or your workspace
    git clone https://github.com/gyxxyg/TRACE.git
    cd TRACE
    pip install -r requirements.txt
    pip install -e .                  # registers the `trace` package
    cd ..

Then set TRACE_REPO_DIR or rely on the default `import trace.*` after that
install. On Colab T4 we additionally need:

    pip install bitsandbytes accelerate

## Hardware

`Yongxin-Guo/trace-uni` is ~15 GB fp16. With `load_in_4bit=True` it consumes
~5-6 GB weight VRAM; peak (KV cache + 64-frame visual tokens) ≈ 10-12 GB on
T4. Per-query latency ≈ 10-30 s on T4 4-bit.

Reference inference script we mirror:
    https://github.com/gyxxyg/TRACE/blob/master/scripts/inference/inference.py
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import numpy as np

from jockey.open_source.moment_localizer import MomentPrediction

log = logging.getLogger(__name__)


# Special token IDs from TRACE's tokenizer. Pulled verbatim from inference.py
# so the parser stays in lockstep with the published checkpoint.
_CAPTION_MAX_ID = 32000
_TIME_SYNC_TOKEN = 32001     # <sync> marker for the end of a timestamp block
_TIME_SEP_TOKEN  = 32002     # <sep>  between two timestamps inside a block
_SCORE_BASE_ID   = 32013
_SCORE_SYNC_TOKEN = 32014    # <sync> for score block
_SCORE_SEP_TOKEN  = 32015    # <sep>  between scores


def _parse_trace_output(output_ids, tokenizer, model) -> dict:
    """Decode TRACE's interleaved (timestamps | scores | captions) token stream.

    Returns: {"timestamps": [[start, end], ...], "scores": [[s, ...], ...],
              "captions": ["...", ...]}

    Mirrors the parsing loop in TRACE's `scripts/inference/inference.py`.
    """
    outputs = {"timestamps": [], "scores": [], "captions": []}
    cur_timestamps: List[float] = []
    cur_timestamp: List[str] = []
    cur_scores: List[float] = []
    cur_score: List[str] = []
    cur_caption: List[int] = []

    time_tok = model.get_model().time_tokenizer
    score_tok = model.get_model().score_tokenizer

    for idx in output_ids[0]:
        idx_v = int(idx)
        if idx_v <= _CAPTION_MAX_ID:
            if idx_v == _CAPTION_MAX_ID:
                outputs["captions"].append(tokenizer.decode(cur_caption, skip_special_tokens=True))
                cur_caption = []
            else:
                cur_caption.append(idx_v)
        elif idx_v <= _SCORE_BASE_ID:                        # 32001..32013 = timestamp tokens
            if idx_v == _TIME_SYNC_TOKEN:
                if cur_timestamp:
                    cur_timestamps.append(float("".join(cur_timestamp)))
                outputs["timestamps"].append(cur_timestamps)
                cur_timestamps = []
                cur_timestamp = []
            elif idx_v == _TIME_SEP_TOKEN:
                if cur_timestamp:
                    cur_timestamps.append(float("".join(cur_timestamp)))
                cur_timestamp = []
            else:
                cur_timestamp.append(time_tok.decode(idx_v - _TIME_SYNC_TOKEN))
        else:                                                # 32014+ = score tokens
            if idx_v == _SCORE_SYNC_TOKEN:
                if cur_score:
                    cur_scores.append(float("".join(cur_score)))
                outputs["scores"].append(cur_scores)
                cur_scores = []
                cur_score = []
            elif idx_v == _SCORE_SEP_TOKEN:
                if cur_score:
                    cur_scores.append(float("".join(cur_score)))
                cur_score = []
            else:
                cur_score.append(score_tok.decode(idx_v - _SCORE_SYNC_TOKEN))

    if cur_caption:
        outputs["captions"].append(tokenizer.decode(cur_caption, skip_special_tokens=True))
    return outputs


class TraceLocalizer:
    """Grounding backend that uses TRACE (e.g. `Yongxin-Guo/trace-uni`) to
    predict (start, end) timestamps for a (query, video) pair.

    Lazy-loads on first `.localize` call. Subsequent calls reuse the loaded
    model. NOT thread-safe — wrap in a lock if calling from async workers.
    """

    def __init__(
        self,
        model_path: str = "Yongxin-Guo/trace-uni",
        device: str = "cuda",
        load_in_4bit: bool = True,
        num_frames: int = 64,
        conv_mode: str = "llama_2",
    ):
        self.model_path = model_path
        self.device = device
        self.load_in_4bit = load_in_4bit
        self.num_frames = num_frames
        self.conv_mode = conv_mode

        self._model = None
        self._tokenizer = None
        self._processor = None
        self._trace_modules = None  # cached import handles

    def _import_trace(self):
        """Import the TRACE Python package. Raise with install instructions if missing."""
        if self._trace_modules is not None:
            return self._trace_modules
        try:
            from trace.conversation import conv_templates, SeparatorStyle
            from trace.constants import DEFAULT_MMODAL_TOKEN, MMODAL_TOKEN_INDEX
            from trace.mm_utils import (
                get_model_name_from_path, tokenizer_MMODAL_token_all,
                process_video, process_image, KeywordsStoppingCriteria,
            )
            from trace.model.builder import load_pretrained_model
        except ImportError as e:
            raise ImportError(
                f"Could not import the TRACE package ({e}). TRACE ships a custom\n"
                f"TraceMistralForCausalLM architecture that requires the github repo:\n"
                f"\n"
                f"    git clone https://github.com/gyxxyg/TRACE.git\n"
                f"    cd TRACE && pip install -r requirements.txt && pip install -e .\n"
                f"\n"
                f"If running on Colab, also: pip install bitsandbytes accelerate"
            )
        self._trace_modules = {
            "conv_templates": conv_templates,
            "SeparatorStyle": SeparatorStyle,
            "DEFAULT_MMODAL_TOKEN": DEFAULT_MMODAL_TOKEN,
            "MMODAL_TOKEN_INDEX": MMODAL_TOKEN_INDEX,
            "get_model_name_from_path": get_model_name_from_path,
            "tokenizer_MMODAL_token_all": tokenizer_MMODAL_token_all,
            "process_video": process_video,
            "process_image": process_image,
            "KeywordsStoppingCriteria": KeywordsStoppingCriteria,
            "load_pretrained_model": load_pretrained_model,
        }
        return self._trace_modules

    def _load(self) -> None:
        if self._model is not None:
            return
        t = self._import_trace()

        log.info(f"Loading TRACE model from {self.model_path} (4bit={self.load_in_4bit})...")
        model_name = t["get_model_name_from_path"](self.model_path)
        # TRACE's load_pretrained_model is forked from VideoLLaMA2 and accepts
        # load_4bit / load_8bit kwargs that map to bitsandbytes config.
        tokenizer, model, processor, _ctx = t["load_pretrained_model"](
            self.model_path, None, model_name,
            load_4bit=self.load_in_4bit, load_8bit=False,
        )
        # When 4bit-quantized, accelerate has already placed weights on the
        # right device; .to() is a no-op (and would error). Only move for fp16.
        if not self.load_in_4bit:
            model = model.to(self.device)
        self._model = model
        self._tokenizer = tokenizer
        self._processor = processor
        log.info("TRACE model loaded.")

    def localize(self, query: str, video_path: str) -> MomentPrediction:
        """Predict the moment matching `query` in `video_path`. All times in seconds."""
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self._load()
        t = self._import_trace()
        import torch

        # ----- preprocess video -----
        tensor, video_timestamps = t["process_video"](
            video_path, self._processor,
            self._model.config.image_aspect_ratio,
            num_frames=self.num_frames,
        )
        tensor = tensor.to(dtype=torch.float16, device=self.device, non_blocking=True)
        tensor = [tensor]
        video_timestamps_list = [video_timestamps]
        heads = [1]
        modal_list = ["video"]
        default_mm_token = t["DEFAULT_MMODAL_TOKEN"]["VIDEO"]

        # ----- build prompt (Charades-STA-style moment retrieval) -----
        question_text = (
            f"Localize the visual content described by the given textual query "
            f"'{query}' in the video, and output the start and end timestamps in seconds."
        )
        conv = t["conv_templates"][self.conv_mode].copy()
        conv.append_message(conv.roles[0], default_mm_token + "\n" + question_text)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt() + "<sync>"

        input_ids = t["tokenizer_MMODAL_token_all"](
            prompt, self._tokenizer, return_tensors="pt"
        ).unsqueeze(0).to(self.device)
        attention_masks = input_ids.ne(self._tokenizer.pad_token_id).long().to(self.device)

        # ----- generate -----
        with torch.inference_mode():
            output_ids = self._model.generate(
                input_ids,
                attention_mask=attention_masks,
                images_or_videos=tensor,
                modal_list=modal_list,
                do_sample=False,            # deterministic for reproducibility
                temperature=0.0,
                max_new_tokens=256,         # moment retrieval needs few tokens; cap low
                use_cache=True,
                pad_token_id=self._tokenizer.eos_token_id,
                video_timestamps=video_timestamps_list,
                heads=heads,
            )

        # ----- parse timestamps + scores from interleaved output -----
        parsed = _parse_trace_output(output_ids, self._tokenizer, self._model)
        start_sec, end_sec, confidence = _extract_first_span(parsed)

        duration = float(video_timestamps[-1]) if len(video_timestamps) else 0.0
        return MomentPrediction(
            video_id=os.path.splitext(os.path.basename(video_path))[0],
            query=query,
            start_sec=float(start_sec),
            end_sec=float(end_sec),
            confidence=float(confidence),
            duration=duration,
            saliency=None,                  # LLM grounder: no per-shot saliency
        )


def _extract_first_span(parsed: dict) -> Tuple[float, float, float]:
    """Pull (start, end, score) from TRACE's interleaved output.

    TRACE may emit multiple (timestamp_pair, score, caption) tuples for dense-
    captioning prompts. For moment retrieval the first event is the answer.
    Falls back to (0, 0, 0) if parsing yields nothing — caller should treat as
    a failed prediction.
    """
    ts_list = parsed.get("timestamps") or []
    sc_list = parsed.get("scores") or []
    if not ts_list or len(ts_list[0]) < 2:
        log.warning(f"TRACE output had no usable timestamps: {parsed!r}")
        return 0.0, 0.0, 0.0
    start, end = ts_list[0][0], ts_list[0][1]
    score = sc_list[0][0] if sc_list and sc_list[0] else 1.0
    if end < start:
        start, end = end, start
    return float(start), float(end), float(score)
