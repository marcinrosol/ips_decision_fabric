"""Which local Ollama model the agent and MCP server use. Machine-specific --
scripts/setup.py detects available GPU VRAM and writes its choice to
agents/model.txt (gitignored, not portable across machines). Falls back to
the smallest supported tier if that file is missing, e.g. on a checkout that
skipped setup."""

from pathlib import Path

MODEL_FILE = Path(__file__).parent / "model.txt"
DEFAULT_MODEL = "qwen2.5:7b"


def get_model() -> str:
    if MODEL_FILE.exists():
        model = MODEL_FILE.read_text(encoding="utf-8").strip()
        if model:
            return model
    return DEFAULT_MODEL
