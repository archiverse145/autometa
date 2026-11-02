import os
from pathlib import Path
import imageio_ffmpeg

# Base directories
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = BASE_DIR / "pipeline.db"
ENV_PATH = BASE_DIR / ".env"

# Auto-load .env file if present
if ENV_PATH.exists():
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# Binaries
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# API Keys & Credentials (can be overridden by environment variables or .env)
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")

# Voice settings (natural, authoritative voice, slightly faster for Reels)
DEFAULT_VOICE = "en-US-ChristopherNeural"
SPEECH_RATE = "+25%"  # 1.25x spoken speed; captions stay aligned with TTS timestamps
