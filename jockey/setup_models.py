"""
Setup Script — Install dependencies and download HuggingFace models.

Downloads and caches locally:
  - ViCLIP (OpenGVLab/ViCLIP) — video encoder
  - wav2vec2 (facebook/wav2vec2-base-960h) — audio encoder

Installs pip packages:
  - transformers, torch, decord, qdrant-client, openai, Pillow, scenedetect

Usage:
    python setup_models.py
    python setup_models.py --models-only     # skip pip install
    python setup_models.py --deps-only       # skip model download
    python setup_models.py --device cpu      # test on CPU
"""
import argparse
import logging
import os
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("setup")

# Load .env file
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# Models to download
MODELS = {
    "clip": {
        "repo_id": "openai/clip-vit-large-patch14",
        "description": "CLIP ViT-L/14 video+text encoder (768-dim, ~890MB)",
        "type": "model",
    },
    "wav2vec2": {
        "repo_id": "facebook/wav2vec2-base-960h",
        "description": "wav2vec2 audio encoder (95M params, 768-dim)",
        "type": "model",
    },
}

# Required pip packages
REQUIRED_PACKAGES = [
    "torch",
    "transformers",
    "qdrant-client",
    "openai",
    "Pillow",
    "numpy",
    "decord",
    "huggingface_hub",
]

OPTIONAL_PACKAGES = [
    "scenedetect[opencv]",    # shot boundary detection
    "sherpa-onnx",            # ZipFormer ASR
    "accelerate",             # for large model loading
]


def install_dependencies(include_optional: bool = False):
    """Install required pip packages."""
    log.info("=" * 60)
    log.info("INSTALLING DEPENDENCIES")
    log.info("=" * 60)

    packages = REQUIRED_PACKAGES.copy()
    if include_optional:
        packages.extend(OPTIONAL_PACKAGES)

    for pkg in packages:
        log.info(f"  Installing {pkg}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                check=True,
                capture_output=True,
                text=True,
            )
            log.info(f"    OK - {pkg}")
        except subprocess.CalledProcessError as e:
            log.warning(f"    FAILED - {pkg}: {e.stderr.strip().split(chr(10))[-1]}")


def download_models(device: str = "cpu"):
    """Download and cache HuggingFace models."""
    log.info("")
    log.info("=" * 60)
    log.info("DOWNLOADING HUGGINGFACE MODELS")
    log.info("=" * 60)

    # Login to HuggingFace if token available
    hf_token = os.environ.get("HF_API_KEY", "")
    if hf_token:
        try:
            from huggingface_hub import login
            login(token=hf_token, add_to_git_credential=False)
            log.info("  Logged in to HuggingFace")
        except Exception as e:
            log.warning(f"  HF login failed: {e}")
    else:
        log.warning("  HF_API_KEY not set — some models may not be accessible")

    for name, info in MODELS.items():
        repo_id = info["repo_id"]
        log.info(f"\n  [{name}] {info['description']}")
        log.info(f"  Repo: {repo_id}")

        try:
            from huggingface_hub import snapshot_download
            log.info(f"  Downloading {repo_id}...")
            path = snapshot_download(
                repo_id=repo_id,
                token=hf_token or None,
                local_dir_use_symlinks=False,
            )
            log.info(f"    OK - Cached at: {path}")
        except Exception as e:
            log.warning(f"    FAILED to download {repo_id}: {e}")
            log.info(f"    The model will be downloaded on first use instead.")

    # Verify models can load
    log.info("")
    log.info("=" * 60)
    log.info("VERIFYING MODELS")
    log.info("=" * 60)

    # Test wav2vec2
    log.info("\n  [wav2vec2] Testing load...")
    try:
        from transformers import Wav2Vec2Model, Wav2Vec2Processor
        processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
        model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base-960h")
        model = model.to(device).eval()
        param_count = sum(p.numel() for p in model.parameters())
        log.info(f"    OK - wav2vec2 loaded ({param_count:,} params, device={device})")
        del model, processor
    except Exception as e:
        log.warning(f"    FAILED: {e}")

    # Test CLIP
    log.info("\n  [CLIP] Testing load...")
    try:
        from transformers import CLIPModel
        model = CLIPModel.from_pretrained(
            "openai/clip-vit-large-patch14",
            token=hf_token or None,
        )
        model = model.to(device).eval()
        param_count = sum(p.numel() for p in model.parameters())
        log.info(f"    OK - CLIP loaded ({param_count:,} params, device={device})")
        del model
    except Exception as e:
        log.warning(f"    FAILED: {e}")
        log.info("    CLIP will use placeholder embeddings until the model is available.")

    # Free GPU memory
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def verify_openrouter():
    """Check if OpenRouter API key is configured."""
    log.info("")
    log.info("=" * 60)
    log.info("CHECKING OPENROUTER API")
    log.info("=" * 60)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        log.info(f"  OPENROUTER_API_KEY: set ({api_key[:8]}...)")

        # Test the API
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

            # Test embedding
            log.info("  Testing text embedding (openai/text-embedding-3-large)...")
            response = client.embeddings.create(
                input="test",
                model="openai/text-embedding-3-large",
            )
            dim = len(response.data[0].embedding)
            log.info(f"    OK - Embedding dim: {dim}")

            # Test VLM (just a text prompt, no image)
            log.info("  Testing VLM (qwen/qwen3-vl-8b-instruct)...")
            response = client.chat.completions.create(
                model="qwen/qwen3-vl-8b-instruct",
                messages=[{"role": "user", "content": "Say hello in one word."}],
                max_tokens=10,
            )
            reply = response.choices[0].message.content.strip()
            log.info(f"    OK - VLM response: \"{reply}\"")

        except Exception as e:
            log.warning(f"    API test failed: {e}")
    else:
        log.warning("  OPENROUTER_API_KEY not set!")
        log.info("  Set it with:")
        log.info("    Windows:  set OPENROUTER_API_KEY=sk-or-v1-...")
        log.info("    Linux:    export OPENROUTER_API_KEY=sk-or-v1-...")
        log.info("  Get a key at: https://openrouter.ai/keys")


def print_summary():
    """Print final setup summary."""
    log.info("")
    log.info("=" * 60)
    log.info("SETUP COMPLETE")
    log.info("=" * 60)
    log.info("")
    log.info("API Models (via OpenRouter):")
    log.info("  - openai/text-embedding-3-large  (text embeddings, 3072-dim)")
    log.info("  - qwen/qwen3-vl-8b-instruct      (video Q&A / VLM)")
    log.info("")
    log.info("Local Models (via HuggingFace):")
    log.info("  - openai/clip-vit-large-patch14              (video+text, 768-dim, ~890MB)")
    log.info("  - facebook/wav2vec2-base-960h                (audio, 768-dim, ~380MB)")
    log.info("")
    log.info("Run the pipeline:")
    log.info("  python jockey/open_source/test_mediafm_pipeline.py   # smoke test")
    log.info("  python jockey/run_mediafm_pipeline.py --video vid.mp4  # full pipeline")


def main():
    parser = argparse.ArgumentParser(description="Setup MediaFM Pipeline — install deps and download models")
    parser.add_argument("--models-only", action="store_true", help="Skip pip install, only download models")
    parser.add_argument("--deps-only", action="store_true", help="Skip model download, only install pip packages")
    parser.add_argument("--with-optional", action="store_true", help="Install optional packages too (scenedetect, sherpa-onnx)")
    parser.add_argument("--device", default="cpu", help="Device for model verification (cpu/cuda)")
    parser.add_argument("--skip-verify", action="store_true", help="Skip model loading verification")

    args = parser.parse_args()

    if not args.models_only:
        install_dependencies(include_optional=args.with_optional)

    if not args.deps_only:
        download_models(device=args.device)

    verify_openrouter()
    print_summary()


if __name__ == "__main__":
    main()
