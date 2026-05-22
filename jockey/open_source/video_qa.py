"""
Video Q&A module using OpenRouter API (qwen/qwen3-vl-8b-instruct).

Replaces local Qwen2-VL model with OpenRouter API call.
Sends extracted frames as base64 images to the VLM endpoint.

Usage:
    qa = VideoQA.from_config(config)
    answer = await qa.freeform("What is happening?", video_path="clip.mp4")
    summary = await qa.summarize(video_path="clip.mp4", mode="summary")
"""
import base64
import json
import logging
import os
from typing import List, Optional

import numpy as np

log = logging.getLogger(__name__)


def _frames_to_base64_images(frames: np.ndarray, max_images: int = 8) -> List[str]:
    """Convert numpy frames [N, H, W, 3] to base64-encoded JPEG strings."""
    try:
        from PIL import Image
        import io

        images = []
        # Sample evenly if too many frames
        indices = np.linspace(0, len(frames) - 1, min(max_images, len(frames)), dtype=int)

        for idx in indices:
            frame = frames[idx]
            img = Image.fromarray(frame)
            # Resize to reasonable size for API
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            images.append(b64)

        return images
    except ImportError:
        log.warning("Pillow not installed. pip install Pillow")
        return []


class VideoQA:
    """Video Q&A via OpenRouter API using qwen/qwen3-vl-8b-instruct.

    Sends extracted video frames as images to the VLM for understanding.
    Handles all TwelveLabs Pegasus replacement tasks:
    - gist (title, topics, hashtags)
    - summarize (summary, highlights, chapters)
    - freeform (arbitrary Q&A about video content)
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "qwen/qwen3-vl-8b-instruct",
        base_url: str = "https://openrouter.ai/api/v1",
        max_frames: int = 8,
    ):
        self.model = model
        self.base_url = base_url
        self.max_frames = max_frames
        self._client = None
        self._api_key = api_key

    @classmethod
    def from_config(cls, config):
        """Create a VideoQA from a PipelineConfig."""
        return cls(
            api_key=config.openrouter_api_key,
            model=config.vlm_model,
            base_url=config.openrouter_base_url,
        )

    def _lazy_load(self):
        if self._client is not None:
            return
        if not self._api_key:
            log.warning("OPENROUTER_API_KEY not set. VideoQA will return placeholder responses.")
            self._client = "unavailable"
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
            )
            log.info(f"OpenRouter VLM client initialized (model={self.model})")
        except ImportError:
            log.warning("openai package not installed. pip install openai")
            self._client = "unavailable"

    def _extract_frames(
        self,
        video_path: str,
        start_sec: float = 0.0,
        end_sec: Optional[float] = None,
    ) -> np.ndarray:
        """Extract frames for VLM input.

        Defaults to whole-video sampling (start=0, end=video duration). Pass
        an explicit `[start_sec, end_sec]` to restrict sampling to a window,
        which is what `analyze_range` uses for time-range Q&A.
        """
        try:
            from jockey.open_source.indexer import extract_frames
            # Use a large sentinel for end if not specified; extract_frames clamps
            # internally to the actual video duration.
            end = 9999.0 if end_sec is None else float(end_sec)
            frames = extract_frames(video_path, float(start_sec), end, max_frames=self.max_frames)
            return frames
        except Exception as e:
            log.warning(f"Frame extraction failed: {e}")
            return np.zeros((1, 224, 224, 3), dtype=np.uint8)

    def _generate(
        self,
        video_path: str,
        prompt: str,
        max_tokens: int = 512,
        start_sec: float = 0.0,
        end_sec: Optional[float] = None,
    ) -> str:
        """Core generation: sample frames from `[start_sec, end_sec]`, send + prompt to VLM."""
        self._lazy_load()

        if self._client == "unavailable":
            return f"[VLM unavailable — set OPENROUTER_API_KEY] Prompt was: {prompt}"

        frames = self._extract_frames(video_path, start_sec=start_sec, end_sec=end_sec)
        b64_images = _frames_to_base64_images(frames, max_images=self.max_frames)

        if not b64_images:
            return f"[Could not extract frames from {video_path}] Prompt was: {prompt}"

        # Build message with images
        content = []
        for b64 in b64_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        content.append({"type": "text", "text": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.warning(f"OpenRouter VLM call failed: {e}")
            return f"[VLM error: {e}] Prompt was: {prompt}"

    async def gist(self, video_path: str, options: list) -> str:
        """Generate gist output: title, topics, hashtags.

        Args:
            video_path: Path to video file.
            options: List of requested outputs, e.g. ["title", "topic", "hashtag"].

        Returns:
            JSON string with requested gist outputs.
        """
        result = {}

        if "title" in options:
            result["title"] = self._generate(
                video_path,
                "Generate a concise, descriptive title for this video. Respond with only the title.",
                max_tokens=50,
            )

        if "topic" in options:
            result["topic"] = self._generate(
                video_path,
                "In 1-2 sentences, describe the main topic of this video. Be concise.",
                max_tokens=100,
            )

        if "hashtag" in options:
            hashtags_text = self._generate(
                video_path,
                "Generate 5-10 relevant hashtags for this video. Respond with only the hashtags.",
                max_tokens=100,
            )
            result["hashtag"] = [h.strip() for h in hashtags_text.split() if h.startswith("#")]

        return json.dumps(result)

    async def summarize(self, video_path: str, mode: str = "summary", prompt: Optional[str] = None) -> str:
        """Generate summary, highlights, or chapters.

        Args:
            video_path: Path to video file.
            mode: One of "summary", "highlight", "chapter".
            prompt: Optional additional instructions.

        Returns:
            JSON string with the generated text.
        """
        base_prompts = {
            "summary": "Provide a detailed summary of this video. Include key events and topics discussed.",
            "highlight": (
                "Identify the key highlights of this video. For each highlight, provide:\n"
                "- A short title\n"
                "- The approximate timestamp\n"
                "- A brief description\n"
                "Format as a numbered list."
            ),
            "chapter": (
                "Break this video into logical chapters. For each chapter, provide:\n"
                "- Chapter title\n"
                "- Start time (approximate)\n"
                "- Brief description\n"
                "Format as a numbered list."
            ),
        }

        system = base_prompts.get(mode, base_prompts["summary"])
        if prompt:
            system = f"{system}\n\nAdditional instructions: {prompt}"

        text = self._generate(video_path, system, max_tokens=512)
        return json.dumps({"type": mode, "text": text, "video_url": video_path})

    async def freeform(self, video_path: str, prompt: str) -> str:
        """Answer any question about a video.

        Args:
            video_path: Path to video file.
            prompt: The question or instruction.

        Returns:
            JSON string with the response.
        """
        text = self._generate(video_path, prompt, max_tokens=512)
        return json.dumps({"text": text, "video_url": video_path})

    async def analyze_range(
        self,
        video_path: str,
        start_sec: float,
        end_sec: float,
        prompt: Optional[str] = None,
    ) -> str:
        """Describe what happens in a specific `[start_sec, end_sec]` window of a video.

        Used by the `time-range-analysis` agent tool: the user supplies the time
        range (e.g. "0:09 - 0:12"); we sample N frames from that window only and
        ask the VLM to describe them. NOT to be confused with moment retrieval —
        we are NOT predicting timestamps here, we are *given* them.

        Args:
            video_path: Path to video file.
            start_sec: Window start (seconds).
            end_sec: Window end (seconds, exclusive).
            prompt: Optional override. Defaults to a "describe what happens" prompt.

        Returns:
            JSON string with `{type, text, start, end, video_url}`.
        """
        if end_sec <= start_sec:
            return json.dumps({
                "error": f"end_sec ({end_sec}) must be greater than start_sec ({start_sec})",
                "video_url": video_path,
            })

        if prompt is None or not prompt.strip():
            prompt = (
                f"Describe what happens in the video between {start_sec:.1f}s and "
                f"{end_sec:.1f}s. Focus on visible actions, objects, and people. "
                f"Be concise — 2 to 4 sentences."
            )

        text = self._generate(
            video_path, prompt, max_tokens=512,
            start_sec=float(start_sec), end_sec=float(end_sec),
        )
        return json.dumps({
            "type": "time_range",
            "start": float(start_sec),
            "end": float(end_sec),
            "text": text,
            "video_url": video_path,
        })
