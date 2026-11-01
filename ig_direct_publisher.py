import os
import sys
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    TwoFactorRequired,
    BadPassword,
    PleaseWaitFewMinutes,
    LoginRequired
)
from config import BASE_DIR

SESSION_FILE = BASE_DIR / "ig_session.json"

def get_instagram_client(username: str, password: str) -> Client:
    """
    Logs into Instagram securely using instagrapi on your local machine.
    Saves a persistent session.json file so future runs do not trigger security checkpoints.
    """
    cl = Client()
    # cl uses instagrapi's authentic built-in device profile by default

    # Check if a saved session exists first
    if SESSION_FILE.exists():
        print("[+] Found existing Instagram session. Attempting session restore...")
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            print("[OK] Logged in successfully using saved session!")
            return cl
        except Exception as e:
            print(f"[!] Session restore expired or invalid: {e}. Logging in with credentials...")

    # Fresh login
    try:
        print(f"[+] Logging into Instagram as @{username}...")
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        print(f"[OK] Logged in successfully! Session saved to {SESSION_FILE.name}")
        return cl
    except TwoFactorRequired:
        print("[!] Two-Factor Authentication (2FA) is enabled on this account.")
        code = input(">> Enter the 2FA SMS/Authenticator code: ").strip()
        cl.login(username, password, verification_code=code)
        cl.dump_settings(SESSION_FILE)
        return cl
    except ChallengeRequired:
        print("[!] Instagram triggered a security challenge (SMS or Email verification).")
        # Let user handle challenge
        cl.challenge_resolve(cl.last_json)
        cl.dump_settings(SESSION_FILE)
        return cl
    except BadPassword:
        raise ValueError("[!] Invalid password for this Instagram account.")
    except Exception as e:
        raise RuntimeError(f"[!] Instagram login error: {e}")

def extract_thumbnail(video_path: Path) -> Path:
    """
    Extracts a high quality frame from second 1 of the video using native FFmpeg
    to serve as the Instagram Reel thumbnail.
    """
    from config import FFMPEG_EXE
    thumb_path = video_path.with_suffix(".jpg")
    cmd = [
        FFMPEG_EXE, "-y",
        "-ss", "00:00:01",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(thumb_path)
    ]
    import subprocess
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return thumb_path

def upload_reel_and_logout(video_path: Path, caption: str, username: str, password: str):
    """
    STRICT USER PRIVACY & CONTROL:
    1. Loads the verified local device session.
    2. Generates thumbnail via FFmpeg.
    3. Uploads the Reel.
    4. Closes all network sockets and exits cleanly.
    """
    cl = get_instagram_client(username, password)
    try:
        print(f"\n[+] Extracting high-res thumbnail with FFmpeg...")
        thumbnail_path = extract_thumbnail(video_path)

        print(f"[+] Uploading Reel: {video_path.name} to @{username}...")
        media = cl.clip_upload(
            path=video_path,
            caption=caption,
            thumbnail=thumbnail_path
        )
        print(f"[OK] Reel successfully posted live to Instagram! (Media PK: {media.pk})")
        return media
    finally:
        # Close connection cleanly to stay offline
        try:
            cl.session.close()
        except Exception:
            pass
        print("=" * 60)
        print(f"[✓] SESSION CLOSED: Disconnected from @{username}")
        print("[✓] STATUS: Engine is offline and dormant. Zero background activity.")
        print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        u = sys.argv[1]
        p = sys.argv[2]
        cl = get_instagram_client(u, p)
        print(f"Verified login for @{cl.username} (ID: {cl.user_id})")
