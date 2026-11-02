import os
import random
import requests
import subprocess
from pathlib import Path
from config import TEMP_DIR, ASSETS_DIR, PEXELS_API_KEY, FFMPEG_EXE

BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

BG_STYLES = {
    "satisfying": {
        "keywords": ["satisfying", "sand", "slime", "kinetic", "asmr", "soap"],
        "speed": 2.0,
        "pexels_queries": ["satisfying kinetic sand", "satisfying slime", "oddly satisfying"],
    },
    "minecraft": {
        "keywords": ["minecraft", "parkour"],
        "speed": 1.0,
        "pexels_queries": ["minecraft gameplay", "blocky game parkour"],
    },
    "race": {
        "keywords": ["race", "racing", "gta", "drive", "f1", "needforspeed", "car"],
        "speed": 1.0,
        "pexels_queries": ["formula 1 racing", "street racing car night", "race car cockpit"],
    },
}

def get_local_background_clips() -> list[Path]:
    """Returns all .mp4 files found in assets/backgrounds."""
    return list(BACKGROUNDS_DIR.glob("*.mp4"))


def _clip_matches_style(path: Path, style: str) -> bool:
    name = path.stem.lower().replace("_", " ").replace("-", " ")
    return any(keyword in name for keyword in BG_STYLES[style]["keywords"])


def clips_for_style(style: str) -> list[Path]:
    return [p for p in get_local_background_clips() if _clip_matches_style(p, style)]


def probe_duration(video_path: Path) -> float:
    cmd_dur = [FFMPEG_EXE, "-i", str(video_path)]
    res_dur = subprocess.run(cmd_dur, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    for line in res_dur.stderr.split("\n"):
        if "Duration:" in line:
            parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 60.0


def ensure_race_car_background() -> Path | None:
    """Reuse a local race clip, or download one into assets/backgrounds if an API key exists."""
    existing = clips_for_style("race")
    if existing:
        return existing[0]

    dest = BACKGROUNDS_DIR / "race_car.mp4"
    for query in BG_STYLES["race"]["pexels_queries"]:
        if fetch_pexels_video(query, dest) or fetch_pixabay_video(query, dest):
            print(f"[+] Saved race-car background as {dest.name}")
            return dest
    return None


def pick_background_style(requested: str = "auto") -> str:
    requested = (requested or "auto").lower().strip()
    if requested in BG_STYLES:
        if requested == "race" and not clips_for_style("race"):
            ensure_race_car_background()
        return requested

    available = [style for style in BG_STYLES if clips_for_style(style)]
    if not clips_for_style("race") and ensure_race_car_background():
        available.append("race")
    if not available:
        return "satisfying"
    return random.choice(available)


def slice_background_clip(
    source: Path,
    output_path: Path,
    total_duration: float,
    speed: float = 1.0,
) -> bool:
    """Cut a fresh slice from a long source clip. Satisfying footage is typically played at 2x."""
    speed = max(0.5, float(speed))
    source_needed = total_duration * speed + 1.0
    bg_duration = probe_duration(source)
    max_start = max(0, int(bg_duration - source_needed - 2))
    start_offset = random.randint(8, max_start) if max_start > 12 else 0

    vf_parts = [f"setpts=PTS/{speed}"] if speed != 1.0 else []
    cmd = [
        FFMPEG_EXE, "-y",
        "-ss", str(start_offset),
        "-t", str(source_needed),
        "-i", str(source),
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
    ]
    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])
    cmd.append(str(output_path))

    print(
        f"[+] Background: {source.name} | style speed {speed:.1f}x | "
        f"from {start_offset}s"
    )
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"[!] Error slicing local background: {e}")
        return False

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

def get_broll_clips(
    queries: list[str],
    total_duration: float,
    prefix: str = "reel",
    bg_style: str = "auto",
) -> list[Path]:
    """
    Gets or generates video clips:
    1. Picks a local gameplay/satisfying/race background (satisfying plays at 2x).
    2. Then tries Pexels API if key is present.
    3. Then tries Pixabay API if key is present.
    4. Otherwise generates high-contrast aesthetic animated clips automatically.
    """
    clips = []
    num_scenes = max(1, len(queries) if queries else 1)
    clip_duration = max(3.5, total_duration / num_scenes)

    style = pick_background_style(bg_style)
    style_clips = clips_for_style(style)
    if style == "race" and not style_clips:
        race = ensure_race_car_background()
        if race:
            style_clips = [race]
    if not style_clips:
        style_clips = get_local_background_clips()

    # Strategy 1: Use local background video files if user dropped any into assets/backgrounds/
    if style_clips:
        print(f"[+] Using '{style}' background ({len(style_clips)} matching file(s)).")
        chosen_bg = random.choice(style_clips)
        clip_path = TEMP_DIR / f"{prefix}_broll_0.mp4"
        speed = BG_STYLES.get(style, {}).get("speed", 1.0)
        if slice_background_clip(chosen_bg, clip_path, total_duration, speed=speed):
            return [clip_path]
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
