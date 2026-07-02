"""One-time environment setup for IPS Decision Fabric, Windows only.

Installs Python dependencies, checks/installs Tesseract OCR and Ollama
(system-level, not pip-installable), detects available GPU VRAM to pick an
appropriately-sized local model, and pulls it. Safe to re-run -- every step
skips work that's already done.

Usage: python scripts/setup.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MODEL_FILE = REPO_ROOT / "agents" / "model.txt"

TESSERACT_FALLBACK_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OLLAMA_FALLBACK_PATH = Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"

# (min total VRAM in GB, model tag, approximate quantized footprint)
MODEL_TIERS = [
    (40, "qwen2.5:72b", "~47GB"),
    (16, "qwen2.5:14b", "~9GB"),
    (8, "qwen2.5:7b", "~5GB"),
]
FALLBACK_MODEL = "qwen2.5:7b"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"[setup] running: {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def install_python_deps() -> None:
    _run([sys.executable, "-m", "pip", "install", "-r", str(REPO_ROOT / "requirements.txt")], check=True)


def ensure_tesseract() -> None:
    if shutil.which("tesseract") or TESSERACT_FALLBACK_PATH.exists():
        print("[setup] Tesseract OCR already present.")
        return
    print("[setup] Tesseract OCR not found, installing via winget...")
    result = _run(
        ["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e",
         "--accept-package-agreements", "--accept-source-agreements"]
    )
    if result.returncode != 0:
        print(
            "[setup] Automatic install failed -- install manually:\n"
            "  winget install --id UB-Mannheim.TesseractOCR -e"
        )


def ensure_ollama() -> Path | None:
    """Returns the ollama executable path, or None if it couldn't be found
    even after attempting install (caller should fall back to manual
    instructions rather than fail the whole setup)."""
    which = shutil.which("ollama")
    if which:
        print("[setup] Ollama already present.")
        return Path(which)
    if OLLAMA_FALLBACK_PATH.exists():
        print("[setup] Ollama already present.")
        return OLLAMA_FALLBACK_PATH

    print("[setup] Ollama not found, installing via winget...")
    result = _run(
        ["winget", "install", "--id", "Ollama.Ollama", "-e",
         "--accept-package-agreements", "--accept-source-agreements"]
    )
    if result.returncode != 0:
        print("[setup] Automatic install failed -- install manually: winget install --id Ollama.Ollama -e")
        return None
    if OLLAMA_FALLBACK_PATH.exists():
        return OLLAMA_FALLBACK_PATH
    return shutil.which("ollama")


def detect_total_vram_gb() -> float:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True,
        )
        totals_mb = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        return sum(totals_mb) / 1024
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return 0.0


def pick_model(vram_gb: float) -> str:
    for threshold, model, _footprint in MODEL_TIERS:
        if vram_gb >= threshold:
            return model
    return FALLBACK_MODEL


def ensure_model_pulled(ollama_exe: Path, model: str) -> None:
    _run([str(ollama_exe), "pull", model], check=True)


def main() -> None:
    install_python_deps()
    ensure_tesseract()
    ollama_exe = ensure_ollama()

    vram_gb = detect_total_vram_gb()
    model = pick_model(vram_gb)
    if vram_gb == 0:
        print(
            f"[setup] No NVIDIA GPU detected (or nvidia-smi unavailable) -- "
            f"falling back to {model}, which will run on CPU and be slow."
        )
    else:
        print(f"[setup] Detected ~{vram_gb:.0f}GB total VRAM -- selecting {model}.")

    if ollama_exe is None:
        print(f"[setup] Ollama isn't installed -- once it is, run: ollama pull {model}")
    else:
        ensure_model_pulled(ollama_exe, model)

    MODEL_FILE.write_text(model, encoding="utf-8")
    print(f"[setup] Done. Agent will use '{model}' (recorded in agents/model.txt).")


if __name__ == "__main__":
    main()
