import os
import random
import requests
import subprocess
from pathlib import Path
from config import TEMP_DIR, ASSETS_DIR, PEXELS_API_KEY, FFMPEG_EXE

BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

def get_local_background_clips() -> list[Path]:
    """Returns all .mp4 files found in assets/backgrounds."""
    return list(BACKGROUNDS_DIR.glob("*.mp4"))

def fetch_pexels_video(query: str, output_path: Path, api_key: str = None) -> bool:
    """
    Searches Pexels for a vertical video matching the query and downloads it.
    """
    key = api_key or PEXELS_API_KEY or os.getenv("PEXELS_API_KEY", "")
    if not key:
        return False

    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=3"
    headers = {"Authorization": key}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False

        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            return False

        for video in videos:
            for vfile in video.get("video_files", []):
                if vfile.get("width", 0) <= 1080 and vfile.get("height", 0) >= 1280:
                    download_url = vfile["link"]
                    print(f"[+] Downloading Pexels clip for '{query}'...")
                    v_data = requests.get(download_url, timeout=30)
                    with open(output_path, "wb") as f:
                        f.write(v_data.content)
                    return True

        download_url = videos[0]["video_files"][0]["link"]
        v_data = requests.get(download_url, timeout=30)
        with open(output_path, "wb") as f:
            f.write(v_data.content)
        return True

    except Exception:
        return False

def create_synthetic_background(duration_seconds: float, output_path: Path, hue_offset: int = 0):
    """
    Creates dynamic, aesthetic motion backgrounds using native FFmpeg.
    """
    colors = [
        ("0x0f172a", "0x1e293b"), # Slate Dark
        ("0x18181b", "0x27272a"), # Zinc Dark
        ("0x052e16", "0x064e3b"), # Emerald Deep
        ("0x172554", "0x1e3a8a"), # Navy Blue
        ("0x3b0764", "0x581c87")  # Deep Purple
    ]
    c0, c1 = colors[hue_offset % len(colors)]
    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "lavfi",
        "-i", f"color=c={c0}:s=1080x1920:d={duration_seconds}",
        "-f", "lavfi",
        "-i", f"gradients=s=1080x1920:d={duration_seconds}:c0={c0}:c1={c1}:x0=0:y0=0:x1=1080:y1=1920",
        "-filter_complex", "[0:v][1:v]blend=all_mode='overlay':all_opacity=0.7[v]",
        "-map", "[v]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def fetch_pixabay_video(query: str, output_path: Path, api_key: str = None) -> bool:
    """
    Searches Pixabay for a video matching the query and downloads it (instant free API key).
    """
    key = api_key or os.getenv("PIXABAY_API_KEY", "")
    if not key:
        return False
    url = f"https://pixabay.com/api/videos/?key={key}&q={query}&per_page=3"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return False
        data = resp.json()
        hits = data.get("hits", [])
        if not hits:
            return False
        v_url = hits[0].get("videos", {}).get("medium", {}).get("url") or hits[0].get("videos", {}).get("small", {}).get("url")
        if v_url:
            print(f"[+] Downloading Pixabay clip for '{query}'...")
            v_data = requests.get(v_url, timeout=30)
            with open(output_path, "wb") as f:
                f.write(v_data.content)
            return True
        return False
    except Exception:
        return False

def get_broll_clips(queries: list[str], total_duration: float, prefix: str = "reel") -> list[Path]:
    """
    Gets or generates video clips:
    1. First checks if local video files exist in assets/backgrounds (e.g. gameplay/nature/loops).
    2. Then tries Pexels API if key is present.
    3. Then tries Pixabay API if key is present.
    4. Otherwise generates high-contrast aesthetic animated clips automatically.
    """
    local_bg_files = get_local_background_clips()
    clips = []
    num_scenes = max(1, len(queries))
    clip_duration = max(3.5, total_duration / num_scenes)

    # Strategy 1: Use local background video files if user dropped any into assets/backgrounds/
    if local_bg_files:
        print(f"[+] Found {len(local_bg_files)} local background video(s) in assets/backgrounds!")
        # For continuous gameplay/satisfying footage, grab a single continuous, non-repeating slice!
        chosen_bg = random.choice(local_bg_files)
        clip_path = TEMP_DIR / f"{prefix}_broll_0.mp4"
        
        # Get duration of source video to pick a clean random start point
        cmd_dur = [FFMPEG_EXE, "-i", str(chosen_bg)]
        res_dur = subprocess.run(cmd_dur, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        bg_duration = 60.0
        for line in res_dur.stderr.split("\n"):
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                bg_duration = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                break

        max_start = max(0, int(bg_duration - total_duration - 5))
        # Pick a random start time so every video is fresh and never starts from 00:00
        start_offset = random.randint(10, max_start) if max_start > 15 else 0
        
        print(f"[+] Slicing smooth, non-repeating continuous background from {chosen_bg.name} (from {start_offset}s to {start_offset + int(total_duration)}s)...")
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_offset),
            "-i", str(chosen_bg),
            "-t", str(total_duration + 0.5),
            "-an",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            str(clip_path)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return [clip_path]
        except Exception as e:
            print(f"[!] Error slicing local background: {e}")
            create_synthetic_background(total_duration + 1.0, clip_path)
            return [clip_path]

    # Strategy 2: Try Pexels API
    has_pexels = bool(PEXELS_API_KEY or os.getenv("PEXELS_API_KEY", ""))
    if has_pexels:
        for i, q in enumerate(queries):
            clip_path = TEMP_DIR / f"{prefix}_broll_{i}.mp4"
            if fetch_pexels_video(q, clip_path):
                clips.append(clip_path)
            else:
                create_synthetic_background(clip_duration + 1.0, clip_path, hue_offset=i)
                clips.append(clip_path)
        return clips

    # Strategy 3: Try Pixabay API
    has_pixabay = bool(os.getenv("PIXABAY_API_KEY", ""))
    if has_pixabay:
        for i, q in enumerate(queries):
            clip_path = TEMP_DIR / f"{prefix}_broll_{i}.mp4"
            if fetch_pixabay_video(q, clip_path):
                clips.append(clip_path)
            else:
                create_synthetic_background(clip_duration + 1.0, clip_path, hue_offset=i)
                clips.append(clip_path)
        return clips

    # Strategy 4: Automatic aesthetic motion generation (Zero API keys needed!)
    print("[+] Using automated dark cinematic background generator (No API key required)...")
    for i in range(num_scenes):
        clip_path = TEMP_DIR / f"{prefix}_broll_{i}.mp4"
        create_synthetic_background(clip_duration + 1.0, clip_path, hue_offset=i)
        clips.append(clip_path)

    return clips

if __name__ == "__main__":
    test_out = TEMP_DIR / "test_synth.mp4"
    create_synthetic_background(5.0, test_out)
