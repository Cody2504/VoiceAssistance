"""Jockey runtime utilities.

Substrate-agnostic terminal event parsing + environment-variable checks.
TwelveLabs-specific helpers (`download_video`, `get_video_metadata` against
api.twelvelabs.io) were removed in the open-source migration; their roles
are now filled by `jockey.open_source.search.VideoSearch.get_video_metadata`
and `jockey.open_source.editing_utils.cut_local_clip`.
"""
import os
import sys
import json
import ffmpeg
from dotenv import find_dotenv, load_dotenv
from rich.padding import Padding
from rich.console import Console
from rich.json import JSON


REQUIRED_ENVIRONMENT_VARIABLES = set([
    "OPENROUTER_API_KEY",
    "HOST_PUBLIC_DIR",
    "LLM_PROVIDER",
])
AZURE_ENVIRONMENT_VARIABLES = set([
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "OPENAI_API_VERSION",
])
OPENAI_ENVIRONMENT_VARIABLES = set([
    "OPENAI_API_KEY",
])
ALL_JOCKEY_ENVIRONMENT_VARIABLES = (
    REQUIRED_ENVIRONMENT_VARIABLES
    | AZURE_ENVIRONMENT_VARIABLES
    | OPENAI_ENVIRONMENT_VARIABLES
)


def parse_langchain_events_terminal(event: dict):
    """Pretty-print LangChain stream events to the terminal during local runs."""
    console = Console()

    if event["event"] == "on_chat_model_stream":
        if isinstance(event["data"]["chunk"], dict):
            content = event["data"]["chunk"]["content"]
        else:
            content = event["data"]["chunk"].content

        if content and "instructor" in event["tags"]:
            console.print(f"[red]{content}", end="")
        elif content and "planner" in event["tags"]:
            console.print(f"[yellow]{content}", end="")
        elif content and "supervisor" in event["tags"]:
            console.print(f"[white]{content}", end="")
    elif event["event"] == "on_tool_start":
        tool = event["name"]
        console.print(Padding(f"[cyan]🏇 Using: {tool}", (1, 0, 0, 2)))
        console.print(Padding(f"[cyan]🏇 Inputs:", (0, 2)))
        console.print(Padding(JSON(json.dumps(event["data"]["input"]), indent=2), (1, 6)))
    elif event["event"] == "on_tool_end":
        tool = event["name"]
        console.print(Padding(f"[cyan]🏇 Finished Using: {tool}", (0, 2)))
        console.print(Padding(f"[cyan]🏇 Outputs:", (0, 2)))
        try:
            console.print(Padding(JSON(event["data"]["output"], indent=2), (1, 6)))
        except (json.decoder.JSONDecodeError, TypeError):
            console.print(Padding(str(event["data"]["output"]), (0, 6)))
    elif event["event"] == "on_chat_model_start":
        if "instructor" in event["tags"]:
            console.print(Padding(f"[red]🏇 Instructor: ", (1, 0)), end="")
        elif "planner" in event["tags"]:
            console.print(Padding(f"[yellow]🏇 Planner: ", (1, 0)), end="")
        elif "reflect" in event["tags"]:
            console.print()
            console.print(f"[cyan]🏇 Jockey: ", end="")


def cut_local_clip(video_path: str, start: float, end: float, output_path: str) -> str:
    """Extract `[start, end]` seconds of `video_path` into `output_path` via ffmpeg.

    Replaces the old TwelveLabs `download_video` helper. Used by the
    video-editing stirrup when composing clips. Assumes `video_path` already
    lives on the local filesystem (resolved via `VideoSearch.get_video_metadata`).
    """
    if os.path.isfile(output_path):
        return output_path
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    duration = max(0.0, end - start)
    (
        ffmpeg
        .input(filename=video_path, ss=start, t=duration, loglevel="quiet")
        .output(output_path, vcodec="copy", acodec="copy")
        .overwrite_output()
        .run()
    )
    return output_path


def check_environment_variables():
    """Check that a .env file contains the required environment variables.

    Uses the current working directory tree to search for a .env file.
    """
    load_dotenv(find_dotenv(usecwd=True))

    if REQUIRED_ENVIRONMENT_VARIABLES & os.environ.keys() != REQUIRED_ENVIRONMENT_VARIABLES:
        missing = REQUIRED_ENVIRONMENT_VARIABLES - os.environ.keys()
        print(f"Expected the following environment variables:\n\t{', '.join(REQUIRED_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{', '.join(missing)}")
        sys.exit("Missing required environment variables.")

    if (
        AZURE_ENVIRONMENT_VARIABLES & os.environ.keys() != AZURE_ENVIRONMENT_VARIABLES
        and OPENAI_ENVIRONMENT_VARIABLES & os.environ.keys() != OPENAI_ENVIRONMENT_VARIABLES
    ):
        missing_azure = AZURE_ENVIRONMENT_VARIABLES - os.environ.keys()
        missing_openai = OPENAI_ENVIRONMENT_VARIABLES - os.environ.keys()
        print(f"If using Azure, expected:\n\t{', '.join(AZURE_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{', '.join(missing_azure)}")
        print(f"If using OpenAI, expected:\n\t{', '.join(OPENAI_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{', '.join(missing_openai)}")
        sys.exit("Missing Azure or OpenAI environment variables.")
