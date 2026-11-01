import json
import subprocess
from pathlib import Path
from config import FFMPEG_EXE, TEMP_DIR, OUTPUT_DIR

def get_media_duration(file_path: Path) -> float:
    """
    Returns the duration in seconds of an audio or video file.
    """
    cmd = [
        FFMPEG_EXE, "-i", str(file_path)
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    # Parse Duration: 00:00:12.38
    for line in res.stderr.split("\n"):
        if "Duration:" in line:
            parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
    return 10.0

def normalize_clip(input_clip: Path, output_clip: Path, target_duration: float):
    """
    Scales and crops any video clip into standard 1080x1920 (9:16) portrait format at 30fps.
    """
    # Scale so minimum dimension fills 1080x1920, then crop center
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "fps=30"
    )
    cmd = [
        FFMPEG_EXE, "-y",
        "-stream_loop", "-1",
        "-i", str(input_clip),
        "-t", str(target_duration),
        "-vf", vf,
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(output_clip)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def compose_reel(
    clips: list[Path],
    audio_path: Path,
    ass_path: Path,
    output_filename: str = "final_reel.mp4"
) -> Path:
    """
    Takes a sequence of B-roll video clips, an audio voiceover, and ASS subtitles,
    and renders a high-production 1080x1920 MP4 ready for Instagram Reels.
    """
    total_audio_duration = get_media_duration(audio_path)
    print(f"[+] Total voiceover duration: {total_audio_duration:.2f}s")

    num_clips = max(1, len(clips))
    clip_duration = total_audio_duration / num_clips

    normalized_clips = []
    concat_list_file = TEMP_DIR / "concat_list.txt"

    with open(concat_list_file, "w", encoding="utf-8") as f_concat:
        for idx, clip in enumerate(clips):
            norm_path = TEMP_DIR / f"norm_clip_{idx}.mp4"
            normalize_clip(clip, norm_path, clip_duration + 0.5)
            normalized_clips.append(norm_path)
            # Write absolute path with forward slashes for FFmpeg concat demuxer
            clean_path = str(norm_path.resolve()).replace("\\", "/")
            f_concat.write(f"file '{clean_path}'\n")

    output_path = OUTPUT_DIR / output_filename
    ass_rel_name = ass_path.name
    audio_rel_name = audio_path.name
    concat_rel_name = concat_list_file.name

    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_rel_name,
        "-i", audio_rel_name,
        "-vf", f"ass={ass_rel_name}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path.resolve())
    ]

    print("[+] Rendering final Reel with burned captions...")
    subprocess.run(cmd, cwd=str(TEMP_DIR), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[OK] Reel rendered successfully: {output_path}")

    return output_path

if __name__ == "__main__":
    audio = TEMP_DIR / "reel_voice.mp3"
    ass = TEMP_DIR / "reel_subs.ass"
    broll = [TEMP_DIR / "test_synth.mp4"]
    if audio.exists() and ass.exists():
        compose_reel(broll, audio, ass, "test_complete_reel.mp4")
