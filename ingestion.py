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

def _default_caption(hook: str, story: str) -> str:
    lead = hook.strip() or story.strip()[:120]
    return (
        f"{lead}\n\nWould you have guessed this? Comment below! 👇\n\n"
        "#didyouknow #reels #viral #explore #facts"
    )


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _call_script_llm(system_prompt: str, user_content: str) -> dict | None:
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\nInput Content:\n{user_content}"}]}],
                "generationConfig": {"response_mime_type": "application/json"},
            }
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return _parse_json_object(result_text)
        except Exception as e:
            print(f"[!] Gemini generation error: {e}")

    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=25)
            if resp.status_code == 200:
                result_text = resp.json()["choices"][0]["message"]["content"]
                return _parse_json_object(result_text)
        except Exception as e:
            print(f"[!] Groq generation error: {e}")

    return None


def _ensure_hook_first(narration: str, hook: str) -> str:
    spoken = (narration or "").strip()
    if not hook:
        return spoken
    if spoken.lower().startswith(hook.lower()):
        rest = spoken[len(hook):].lstrip(" .,-")
        return f"{hook} {rest}".strip() if rest else hook
    return f"{hook} {spoken}".strip()


def _local_story_upgrade(hook: str, story: str) -> dict:
    """Punchier narration when no LLM key is configured."""
    clauses = [c.strip(" ,") for c in re.split(r"[.;]\s+", story.strip()) if c.strip()]
    if not clauses:
        clauses = [story.strip().rstrip(".")]
    body_parts = []
    for i, clause in enumerate(clauses):
        sentence = clause[0].upper() + clause[1:] if len(clause) > 1 else clause
        if sentence and not sentence.endswith((".", "?", "!")):
            sentence += "."
        body_parts.append(sentence)
        if i == 0 and len(clauses) > 1:
            body_parts.append("But that is only the part most people never hear.")
    closer = "Would you have done the same? Tell me in the comments."
    if hook:
        narration = f"{hook} {' '.join(body_parts)} {closer}"
        title = hook[:80]
    else:
        chosen_hook = random.choice([
            "This sounds like a movie plot, but it actually happened.",
            "Most people have no idea this is true.",
            "History hid this detail in plain sight.",
        ])
        narration = f"{chosen_hook} {' '.join(body_parts)} {closer}"
        title = "Mind Blowing Mystery"
    return {
        "title": title,
        "narration": narration,
        "broll_queries": ["cinematic vertical", "mysterious dark footage", "ancient history"],
        "ig_caption": _default_caption(hook, story),
    }


def generate_script_with_ai(
    content_text: str,
    audience_learnings: str = "",
    verbatim: bool = False,
    hook: str | None = None,
) -> dict:
    """
    Generates a viral short-form Reel script, visual keywords, and IG caption.
    When a Did-you-know hook is provided, that line is spoken first, then a richer story.
    """
    hook_text = (hook or "").strip()
    story_text = content_text.strip()
    if hook_text and story_text:
        narration = f"{hook_text} {story_text}".strip()
    else:
        narration = story_text

    if verbatim:
        return {
            "title": hook_text[:80] if hook_text else "Viral Story",
            "narration": narration,
            "broll_queries": ["cinematic vertical", "mysterious dark footage"],
            "ig_caption": _default_caption(hook_text, story_text),
        }

    audience = audience_learnings or "Maximize watch time, curiosity, and comments."

    if hook_text:
        system_prompt = f"""You write addictive Did-You-Know Instagram Reels about history, mythology, and mysteries.

HARD RULES:
- The FIRST spoken sentence must be EXACTLY this hook, word for word:
{hook_text}
- Then expand the user's notes into a richer, cinematic story. Keep every factual claim grounded in the source. Do not invent names, dates, or events.
- You MAY add atmosphere, tension, cause-and-effect, and why it still matters.
- Spoken style: short sentences. Concrete images. No hashtags. No stage directions. No 'wait for it'.
- Total narration 90 to 140 words including the hook.

AFTER THE HOOK:
1. Drop the listener into one vivid detail.
2. Escalate with 3 to 5 punchy reveals.
3. Hit the implication or twist.
4. End with one sharp question that makes people comment.

Audience intelligence: {audience}

Return ONLY valid JSON matching this schema:
{{
  "title": "Punchy 3-Word Title",
  "narration": "Full spoken narration. Starts with the exact hook.",
  "broll_queries": ["keyword1", "keyword2", "keyword3"],
  "ig_caption": "Engaging caption asking a specific question with 5 high-reach hashtags."
}}"""
        user_content = f"HOOK (keep exact):\n{hook_text}\n\nSTORY NOTES:\n{story_text}"
    else:
        system_prompt = f"""You are a short-form video copywriter for high-retention Instagram Reels.
Rewrite the given content into an irresistible 25-40 second narration.

1. HOOK (0-3s): Pattern interrupt. Never start with 'Did you know' unless the source already uses it.
2. ESCALATION: Short punchy sentences. Reveal slowly. Every line earns the next.
3. TWIST: The detail that makes it unforgettable.
4. COMMENT BAIT: One open question.

Audience intelligence: {audience}

Return ONLY valid JSON matching this schema:
{{
  "title": "Punchy 3-Word Title",
  "narration": "Full spoken narration script, 90-140 words. Spoken words only.",
  "broll_queries": ["keyword1", "keyword2", "keyword3"],
  "ig_caption": "Engaging caption asking a specific question with 5 high-reach hashtags."
}}"""
        user_content = story_text

    script = _call_script_llm(system_prompt, user_content)
    if script and script.get("narration"):
        script["narration"] = _ensure_hook_first(script["narration"], hook_text)
        if hook_text:
            script["title"] = script.get("title") or hook_text[:80]
            script.setdefault("ig_caption", _default_caption(hook_text, story_text))
            script.setdefault("broll_queries", ["cinematic vertical", "mysterious dark footage"])
        return script

    print("[!] No LLM script available. Using local story upgrade.")
    return _local_story_upgrade(hook_text, story_text)


if __name__ == "__main__":
    test_story = "A man bought a 4-dollar painting at a flea market because he liked the frame. Inside the backing, he found an original copy of the 1776 Declaration of Independence, which later sold for 2.4 million dollars."
    res = generate_script_with_ai(test_story)
    print(json.dumps(res, indent=2))
