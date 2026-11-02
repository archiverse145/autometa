import asyncio
import edge_tts
from pathlib import Path
from config import TEMP_DIR, DEFAULT_VOICE, SPEECH_RATE

def srt_to_ass(srt_content: str, ass_path: Path):
    """
    Converts SRT to stylized ASS subtitles for 1080x1920 Instagram Reels.
    Places bold, high-contrast, black-bordered text in the center/lower-third.
    """
    ass_header = """[Script Info]
Title: Auto-Generated Reels Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,350,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = srt_content.strip().split("\n")
    events = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.isdigit():
            i += 1
            if i < len(lines) and "-->" in lines[i]:
                time_line = lines[i].strip()
                start_raw, end_raw = time_line.split("-->")
                
                # Convert 00:00:00,100 to 0:00:00.10
                def convert_time(t_str):
                    t_str = t_str.strip().replace(",", ".")
                    parts = t_str.split(":")
                    h = int(parts[0])
                    m = parts[1]
                    s = parts[2][:5]
                    return f"{h}:{m}:{s}"

                start_ass = convert_time(start_raw)
                end_ass = convert_time(end_raw)
                
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                    i += 1
                
                text = " \\N ".join(text_lines).upper() # Uppercase for punchy viral Reels look
                events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}")
        else:
            i += 1

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(events))

async def generate_voice_and_subtitles(text: str, voice: str = DEFAULT_VOICE, prefix: str = "reel"):
    """
    Synthesizes speech and produces both audio (.mp3) and styled subtitles (.ass).
    """
    audio_path = TEMP_DIR / f"{prefix}_voice.mp3"
    srt_path = TEMP_DIR / f"{prefix}_subs.srt"
    ass_path = TEMP_DIR / f"{prefix}_subs.ass"

    communicate = edge_tts.Communicate(text, voice, rate=SPEECH_RATE)
    submaker = edge_tts.SubMaker()

    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                submaker.feed(chunk)

    srt_content = submaker.get_srt()
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    srt_to_ass(srt_content, ass_path)

    return {
        "audio_path": audio_path,
        "srt_path": srt_path,
        "ass_path": ass_path
    }

if __name__ == "__main__":
    sample = "Did you know that sharks existed before trees? It's true! Trees appeared 350 million years ago, but sharks have roamed the oceans for over 400 million years."
    res = asyncio.run(generate_voice_and_subtitles(sample))
    print(f"Generated audio at: {res['audio_path']}")
    print(f"Generated styled subtitles at: {res['ass_path']}")
