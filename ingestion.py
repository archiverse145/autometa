import json
import re
import random
import subprocess
import requests
import os
from config import TEMP_DIR

def extract_from_video_url(url: str) -> dict:
    """
    Extracts metadata, title, and description from YouTube or other video platforms using yt-dlp.
    """
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        url
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        title = data.get("title", "")
        description = data.get("description", "")
        tags = data.get("tags", [])
        return {
            "source_type": "url",
            "title": title,
            "text": f"{title}\n\n{description[:500]}",
            "tags": tags
        }
    except Exception as e:
        print(f"[!] Warning: Could not extract full metadata via yt-dlp: {e}")
        return {
            "source_type": "url",
            "title": "Viral Story",
            "text": f"Interesting video story from {url}",
            "tags": []
        }

def generate_script_with_ai(content_text: str, audience_learnings: str = "", verbatim: bool = False) -> dict:
    """
    Generates a viral short-form Reel script, visual keywords, and IG caption.
    Supports verbatim mode, free Gemini API, Groq API, or built-in viral prompt structuring.
    """
    # If the user already gave a finished script, use it directly!
    if verbatim:
        return {
            "title": "Viral Story",
            "narration": content_text.strip(),
            "broll_queries": ["cinematic vertical", "mysterious dark footage"],
            "ig_caption": f"What do you think about this? Comment below! 👇\n\n#reels #viral #explore #trending #shorts"
        }

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")

    system_prompt = f"""You are the world's highest-paid short-form video copywriter (averaging 5M+ views per Reel).
Rewrite the given content into an irresistible, viral 30-45 second narration script using this exact structure:

1. THE PATTERN-INTERRUPT HOOK (Seconds 0-3):
   Start with an intense, curiosity-inducing hook that stops the scroll immediately.
   Examples of tone:
   - "If you ever see this symbol in an abandoned house, leave immediately."
   - "This is the single most terrifying photo ever taken in history..."
   - "A routine flight took off in 1954, but when it landed 35 years later..."
   Never start with 'Did you know' or 'Have you ever heard'.

2. ESCALATION & MYSTERY (Seconds 4-25):
   Short, punchy sentences. Reveal details slowly. Build intense curiosity. Every sentence must make them need to hear the next sentence.

3. THE TWIST / CLIMAX (Seconds 26-35):
   The mind-blowing realization or climax.

4. ENGAGEMENT TRIGGER (Seconds 36-40):
   An open-ended question that forces people to argue in the comments.

Audience intelligence: {audience_learnings or 'Maximize watch time, cliffhangers, and comment wars.'}

Return ONLY valid JSON matching this schema:
{{
  "title": "Punchy 3-Word Title",
  "narration": "Full spoken narration script under 80 words. Spoken words only. No sound effects.",
  "broll_queries": ["keyword1", "keyword2", "keyword3"],
  "ig_caption": "Engaging caption asking a specific question with 5 high-reach hashtags."
}}"""

    # If Gemini API Key is available
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\nInput Content:\n{content_text}"}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(result_text)
        except Exception as e:
            print(f"[!] Gemini generation error: {e}")

    # If Groq API Key is available
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_text}
                ],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                result_text = resp.json()["choices"][0]["message"]["content"]
                return json.loads(result_text)
        except Exception as e:
            print(f"[!] Groq generation error: {e}")

    # Fallback algorithmic viral hook injector if no external LLM key is configured
    clean = content_text.strip().rstrip(".")
    viral_hooks = [
        "This sounds like a movie plot, but it actually happened.",
        "Scientists still can't fully explain this mystery.",
        "Here is a dark reality that will keep you up tonight.",
        "Most people have no idea this exists right under our feet."
    ]
    chosen_hook = random.choice(viral_hooks)
    narration = f"{chosen_hook} {clean}. But the question everyone is asking is... would you survive this?"

    return {
        "title": "Mind Blowing Mystery",
        "narration": narration,
        "broll_queries": ["mysterious dark footage", "cinematic atmosphere"],
        "ig_caption": f"Would you have survived this? Let us know below! 👇\n\n#viral #mystery #reels #explore #facts"
    }

if __name__ == "__main__":
    test_story = "A man bought a 4-dollar painting at a flea market because he liked the frame. Inside the backing, he found an original copy of the 1776 Declaration of Independence, which later sold for 2.4 million dollars."
    res = generate_script_with_ai(test_story)
    print(json.dumps(res, indent=2))
