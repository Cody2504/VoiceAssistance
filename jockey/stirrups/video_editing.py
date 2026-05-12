"""Video-editing stirrup — ffmpeg ops over locally-stored clips.

`combine_clips` previously called `jockey.util.download_video` to fetch clips
from a TwelveLabs HLS URL. After the open-source migration, source videos
live on local disk; we look up each video's path via Qdrant metadata
(`VideoSearch.get_video_metadata`) and cut sub-clips with `cut_local_clip`.
"""
import os
from typing import Dict, List

import ffmpeg
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool

from jockey.prompts import DEFAULT_VIDEO_EDITING_FILE_PATH
from jockey.stirrups.stirrup import Stirrup
from jockey.util import cut_local_clip


# --------------------------------------------------------------------------- schemas

class Clip(BaseModel):
    index_id: str = Field(description="Index ID a video belongs to.")
    video_id: str = Field(description="Video ID a clip belongs to.")
    start: float = Field(description="Clip start time in seconds.")
    end: float = Field(description="Clip end time in seconds.")


class CombineClipsInput(BaseModel):
    clips: List[Clip] = Field(description="Clips to concatenate.")
    output_filename: str = Field(description="Output filename; must end in .mp4.")
    index_id: str = Field(description="Index ID the clips belong to.")


class RemoveSegmentInput(BaseModel):
    video_filepath: str = Field(description="Full path to target video file.")
    start: float = Field(description="Start time of segment to remove, in seconds.")
    end: float = Field(description="End time of segment to remove, in seconds.")


# --------------------------------------------------------------------------- helpers

def _resolve_source_video_path(video_id: str, index_id: str) -> str:
    """Look up the on-disk source video path via Qdrant metadata."""
    from jockey.stirrups.video_search import _get_video_search
    search = _get_video_search()
    meta = search.get_video_metadata(index_id=index_id, video_id=video_id)
    if not isinstance(meta, dict):
        raise FileNotFoundError(f"Video metadata not found for {index_id}/{video_id}")
    path = meta.get("video_path")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"video_path missing or unreadable in metadata: {path!r}")
    return path


# --------------------------------------------------------------------------- tools

@tool("combine-clips", args_schema=CombineClipsInput)
def combine_clips(clips: List[Dict], output_filename: str, index_id: str) -> str:
    """Concatenate the given clips (in order) into a single MP4 and return its path."""
    try:
        out_root = os.path.join(os.environ.get("HOST_PUBLIC_DIR", "/tmp/jockey_videos"), index_id)
        os.makedirs(out_root, exist_ok=True)

        input_streams = []
        for clip in clips:
            video_id = clip.video_id if hasattr(clip, "video_id") else clip["video_id"]
            start = clip.start if hasattr(clip, "start") else clip["start"]
            end = clip.end if hasattr(clip, "end") else clip["end"]

            clip_path = os.path.join(out_root, f"{video_id}_{start}_{end}.mp4")
            if not os.path.isfile(clip_path):
                source_path = _resolve_source_video_path(video_id, index_id)
                cut_local_clip(source_path, float(start), float(end), clip_path)

            video_in = ffmpeg.input(filename=clip_path, loglevel="error").video.filter("setpts", "PTS-STARTPTS")
            audio_in = ffmpeg.input(filename=clip_path, loglevel="error").audio.filter("asetpts", "PTS-STARTPTS")
            input_streams.extend([video_in, audio_in])

        output_filepath = os.path.join(out_root, output_filename)
        ffmpeg.concat(*input_streams, v=1, a=1).output(
            output_filepath, acodec="libmp3lame"
        ).overwrite_output().run()

        return output_filepath
    except Exception as error:
        return {"message": "There was a video editing error.", "error": str(error)}


@tool("remove-segment", args_schema=RemoveSegmentInput)
def remove_segment(video_filepath: str, start: float, end: float) -> str:
    """Remove a [start, end] segment from a video and return the edited file's path."""
    output_filepath = f"{os.path.splitext(video_filepath)[0]}_clipped.mp4"

    left_v = ffmpeg.input(filename=video_filepath, loglevel="quiet").video.filter("trim", start=0, end=start).filter("setpts", "PTS-STARTPTS")
    left_a = ffmpeg.input(filename=video_filepath, loglevel="quiet").audio.filter("atrim", start=0, end=start).filter("asetpts", "PTS-STARTPTS")
    right_v = ffmpeg.input(filename=video_filepath, loglevel="quiet").video.filter("trim", start=end).filter("setpts", "PTS-STARTPTS")
    right_a = ffmpeg.input(filename=video_filepath, loglevel="quiet").audio.filter("atrim", start=end).filter("asetpts", "PTS-STARTPTS")

    ffmpeg.concat(left_v, left_a, right_v, right_a, v=1, a=1).output(
        filename=output_filepath, acodec="libmp3lame"
    ).overwrite_output().run()

    return output_filepath


# --------------------------------------------------------------------------- worker config

video_editing_worker_config = {
    "tools": [combine_clips, remove_segment],
    "worker_prompt_file_path": DEFAULT_VIDEO_EDITING_FILE_PATH,
    "worker_name": "video-editing",
}
VideoEditingWorker = Stirrup(**video_editing_worker_config)
