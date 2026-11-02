import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Configure Windows terminal encoding to UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import OUTPUT_DIR, IG_USERNAME, IG_PASSWORD, IG_USER_ID, IG_ACCESS_TOKEN
from database import init_db, save_rendered_reel, mark_reel_published
from ingestion import extract_from_video_url, generate_script_with_ai
from voiceover import generate_voice_and_subtitles
from broll import get_broll_clips, pick_background_style
from video_engine import compose_reel, get_media_duration
from ig_publisher import publish_reel_to_instagram
from ig_direct_publisher import upload_reel_and_logout
from feedback_agent import analyze_audience_preferences, sync_instagram_insights

def prompt_hook_and_story() -> tuple[str, str]:
    print("\nEnter the Did you know hook first.")
    print("Example: Did you know Gandhari was not blind in Mahabharata?")
    hook = input("Hook > ").strip()
    print("\nNow enter the story / explanation.")
    story = input("Story > ").strip()
    return hook, story


async def run_pipeline(
    content_input: str,
    is_url: bool = False,
    auto_publish: bool = False,
    verbatim: bool = False,
    hook: str | None = None,
    bg_style: str = "auto",
):
    print("=" * 60)
    print("🚀 STARTING AI VIDEO & INSTAGRAM AUTOMATION PIPELINE")
    print("=" * 60)

    # 1. Initialize Database
    init_db()

    # 2. Extract or Ingest Content
    if is_url:
        print(f"[1/6] Extracting content from URL: {content_input}...")
        extracted = extract_from_video_url(content_input)
        raw_text = extracted["text"]
        topic_title = extracted["title"]
        hook_text = None
    else:
        hook_text = (hook or "").strip() or None
        raw_text = content_input
        topic_title = (hook_text or content_input)[:80]
        if hook_text:
            print(f"[1/6] Hook: {hook_text}")
            print(f"      Story: {content_input[:120]}{'...' if len(content_input) > 120 else ''}")
        else:
            print("[1/6] Processing story text input...")

    # 3. Pull audience feedback from past metrics to guide this generation
    print("[2/6] Loading audience preference intelligence...")
    learnings = analyze_audience_preferences()

    # 4. Generate Viral Script & Visual Keywords
    print("[3/6] Building narration (hook first, then story) and Instagram caption...")
    script_data = generate_script_with_ai(
        raw_text,
        audience_learnings=learnings,
        verbatim=verbatim,
        hook=hook_text,
    )
    print(f"      Title: {script_data['title']}")
    print(f"      Narration: {script_data['narration']}")
    print(f"      B-Roll Queries: {script_data['broll_queries']}")
    chosen_bg = pick_background_style(bg_style)
    print(f"      Background: {chosen_bg}" + (" at 2x" if chosen_bg == "satisfying" else ""))

    timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 5. Generate Voiceover and Subtitles
    print("[4/6] Synthesizing human voiceover and burning karaoke subtitles...")
    voice_res = await generate_voice_and_subtitles(script_data["narration"], prefix=timestamp_prefix)
    voice_duration = get_media_duration(Path(voice_res["audio_path"]))

    # 6. Fetch Visual B-Roll (Pexels / Synthetic 9:16 clips)
    print("[5/6] Fetching 9:16 vertical b-roll footage...")
    clips = get_broll_clips(
        script_data["broll_queries"],
        total_duration=max(8.0, voice_duration),
        prefix=timestamp_prefix,
        bg_style=chosen_bg,
    )

    # 7. Render Final Video
    print("[6/6] Assembling and rendering final Reel with FFmpeg...")
    final_video_name = f"reel_{timestamp_prefix}.mp4"
    rendered_video_path = compose_reel(
        clips=clips,
        audio_path=voice_res["audio_path"],
        ass_path=voice_res["ass_path"],
        output_filename=final_video_name
    )

    # Save to Database
    reel_id = save_rendered_reel(
        topic=topic_title,
        script=script_data["narration"],
        keywords=script_data["broll_queries"],
        video_path=str(rendered_video_path),
        caption=script_data["ig_caption"]
    )
    print(f"[OK] Reel saved to pipeline database (ID #{reel_id})")

    # 8. Instagram Upload (STRICT CONTROL: Only executes when explicitly triggered)
    if auto_publish:
        print("\n[+] 'POST NOW' TRIGGER DETECTED: Proceeding with upload...")
        if IG_ACCESS_TOKEN and IG_USER_ID:
            print("[+] Using Official Meta Graph API (Zero-ban verified route)...")
            pub_result = publish_reel_to_instagram(
                video_path_or_url=str(rendered_video_path),
                caption=script_data["ig_caption"]
            )
            if pub_result.get("media_id"):
                mark_reel_published(reel_id, pub_result["media_id"])
        elif IG_USERNAME and IG_PASSWORD:
            try:
                media = upload_reel_and_logout(
                    video_path=rendered_video_path,
                    caption=script_data["ig_caption"],
                    username=IG_USERNAME,
                    password=IG_PASSWORD
                )
                mark_reel_published(reel_id, str(media.pk))
            except Exception as e:
                print(f"[!] Instagram upload error: {e}")
    else:
        print("\n" + "-" * 60)
        print("⏸️  POSTING SKIPPED (SAFE MODE): Video saved in output folder.")
        print("    Account remains 100% LOGGED OUT.")
        print("    To publish this video live, reply 'post now' or add --post-now.")
        print("-" * 60)

    print("\n" + "=" * 60)
    print("🎉 PIPELINE RUN COMPLETE!")
    print(f"🎬 Video File: {rendered_video_path}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous AI Video & Instagram Pipeline")
    parser.add_argument("--hook", type=str, help="The Did you know opening line, spoken first")
    parser.add_argument("--story", type=str, help="The explanation that follows the hook")
    parser.add_argument(
        "--bg",
        choices=["auto", "satisfying", "minecraft", "race"],
        default="auto",
        help="Background: satisfying (2x), minecraft, race, or auto-pick",
    )
    parser.add_argument("--url", type=str, help="Video URL (YouTube/Shorts/etc.) to extract and recreate")
    parser.add_argument("--verbatim", action="store_true", help="Use the exact words provided without rewriting")
    parser.add_argument("--post-now", action="store_true", help="Explicitly authorize login and posting to Instagram")
    parser.add_argument("--publish-last", action="store_true", help="Publish the most recently rendered video from output/")
    parser.add_argument("--sync-stats", action="store_true", help="Sync latest Instagram insights and performance")

    args = parser.parse_args()

    if args.publish_last:
        from database import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, video_path, ig_caption FROM reels ORDER BY id DESC LIMIT 1")
        last_reel = cursor.fetchone()
        conn.close()
        if last_reel:
            video_file = Path(last_reel["video_path"])
            if video_file.exists():
                print(f"[+] Publishing latest rendered video: {video_file.name}")
                if IG_ACCESS_TOKEN and IG_USER_ID:
                    print("[+] Using Official Meta Graph API...")
                    pub_res = publish_reel_to_instagram(str(video_file), last_reel["ig_caption"])
                    if pub_res.get("media_id"):
                        mark_reel_published(last_reel["id"], pub_res["media_id"])
                else:
                    media = upload_reel_and_logout(video_file, last_reel["ig_caption"], IG_USERNAME, IG_PASSWORD)
                    mark_reel_published(last_reel["id"], str(media.pk))
            else:
                print(f"[!] File not found: {video_file}")
        else:
            print("[!] No rendered reels found in database.")
        sys.exit(0)

    if args.sync_stats:
        print("[+] Syncing Instagram analytics...")
        init_db()
        sync_instagram_insights()
        print(analyze_audience_preferences())
        sys.exit(0)

    if args.url:
        asyncio.run(run_pipeline(
            args.url,
            is_url=True,
            auto_publish=args.post_now,
            verbatim=args.verbatim,
            bg_style=args.bg,
        ))
    elif args.story or args.hook:
        hook = args.hook
        story = args.story or ""
        if hook and not story:
            print("Hook received. Enter the story / explanation:")
            story = input("Story > ").strip()
        if not story:
            print("[!] Need a story/explanation after the hook.")
            sys.exit(1)
        asyncio.run(run_pipeline(
            story,
            is_url=False,
            auto_publish=args.post_now,
            verbatim=args.verbatim,
            hook=hook,
            bg_style=args.bg,
        ))
    else:
        hook, story = prompt_hook_and_story()
        if not story:
            print("[!] Need a story/explanation after the hook.")
            sys.exit(1)
        asyncio.run(run_pipeline(
            story,
            is_url=False,
            auto_publish=args.post_now,
            verbatim=args.verbatim,
            hook=hook,
            bg_style=args.bg,
        ))
