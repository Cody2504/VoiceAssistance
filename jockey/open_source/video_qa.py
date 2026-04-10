"""
Video Q&A module using Qwen2-VL-7B for video understanding.
Replaces TwelveLabs Pegasus APIs (gist, summarize, generate).

Usage:
    qa = VideoQA()
    answer = await qa.freeform("What is happening in this video?", video_path="clip.mp4")
    summary = await qa.summarize(video_path="clip.mp4", mode="summary")
"""
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


class VideoQA:
    """Qwen2-VL-7B wrapper for video question answering and text generation.

    Handles all three TwelveLabs Pegasus replacement tasks:
    - gist (title, topics, hashtags)
    - summarize (summary, highlights, chapters)
    - freeform (arbitrary Q&A about video content)
    """

    def __init__(self, model_name: str = "Qwen/Qwen2-VL-7B-Instruct", device: str = "cuda"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None

    def _lazy_load(self):
        if self._model is not None:
            return

        log.info(f"Loading Qwen2-VL from {self.model_name}...")
        try:
            import torch
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

            self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            self._processor = AutoProcessor.from_pretrained(self.model_name)
            log.info("Qwen2-VL loaded successfully.")
        except (ImportError, Exception) as e:
            log.warning(f"Could not load Qwen2-VL: {e}. Video Q&A will return placeholder responses.")
            self._model = "unavailable"

    def _generate(self, video_path: str, prompt: str, max_tokens: int = 512) -> str:
        """Core generation method — sends video + prompt to Qwen2-VL."""
        self._lazy_load()

        if self._model == "unavailable":
            return f"[Qwen2-VL unavailable] Prompt was: {prompt}"

        import torch

        messages = [{
            "role": "user",
            "content": [
                {"type": "video", "video": f"file://{video_path}", "max_pixels": 360 * 420, "fps": 1.0},
                {"type": "text", "text": prompt},
            ],
        }]

        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], videos=[video_path], return_tensors="pt")
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = self._model.generate(**inputs, max_new_tokens=max_tokens)

        # Decode only the generated tokens (skip the input)
        generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
        response = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response.strip()

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
