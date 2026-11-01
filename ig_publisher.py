import time
import requests
import os
from pathlib import Path
from config import IG_USER_ID, IG_ACCESS_TOKEN
from database import mark_reel_published

def upload_video_to_public_host(video_path: Path) -> str:
    """
    Uploads the rendered video to a fast, free CDN to get a public direct MP4 URL 
    that Meta Graph API requires to crawl and process the Reel.
    """
    print(f"[+] Generating public CDN link for Meta's servers...")
    url = "https://catbox.moe/user/api.php"
    with open(video_path, "rb") as f:
        resp = requests.post(
            url,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (video_path.name, f, "video/mp4")},
            timeout=120
        )
    if resp.status_code == 200 and resp.text.startswith("http"):
        public_url = resp.text.strip()
        print(f"[OK] Public CDN URL created: {public_url}")
        return public_url
    else:
        raise RuntimeError(f"Failed to generate public video URL: {resp.text}")

def publish_reel_to_instagram(
    video_path_or_url: str,
    caption: str,
    ig_user_id: str = None,
    access_token: str = None
) -> dict:
    """
    Publishes a video to Instagram Reels using the official Meta Graph API.
    Does NOT use passwords or scraping — zero risk of account ban.
    """
    user_id = ig_user_id or IG_USER_ID or os.getenv("IG_USER_ID", "")
    token = access_token or IG_ACCESS_TOKEN or os.getenv("IG_ACCESS_TOKEN", "")

    if not user_id or not token:
        print("[!] No Meta IG_USER_ID or IG_ACCESS_TOKEN set.")
        print("[!] Running in SIMULATION MODE: Video is ready in output directory.")
        return {
            "status": "SIMULATED",
            "media_id": "simulated_1234567890",
            "message": "Configure IG_USER_ID and IG_ACCESS_TOKEN in config.py or .env to publish live."
        }

    # Ensure video has a public URL for Meta's crawler
    if not video_path_or_url.startswith("http"):
        video_url = upload_video_to_public_host(Path(video_path_or_url))
    else:
        video_url = video_path_or_url

    # Step 1: Create Reel Container
    container_url = f"https://graph.facebook.com/v19.0/{user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token
    }

    print("[+] Creating Instagram Reel container via Meta Graph API...")
    resp = requests.post(container_url, data=payload, timeout=30)
    data = resp.json()

    if "id" not in data:
        raise RuntimeError(f"Failed to create Reel container: {data}")

    creation_id = data["id"]
    print(f"[+] Container created with ID: {creation_id}. Waiting for Meta video processing...")

    # Step 2: Poll container status until FINISHED
    status_url = f"https://graph.facebook.com/v19.0/{creation_id}"
    for attempt in range(20):
        time.sleep(10)
        status_resp = requests.get(status_url, params={"fields": "status_code", "access_token": token}, timeout=15)
        status_data = status_resp.json()
        status_code = status_data.get("status_code", "IN_PROGRESS")
        print(f"    Status: {status_code} (attempt {attempt + 1}/20)...")

        if status_code == "FINISHED":
            break
        elif status_code in ["ERROR", "EXPIRED"]:
            raise RuntimeError(f"Video processing failed on Meta servers: {status_data}")
    else:
        raise TimeoutError("Meta video processing timed out.")

    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v19.0/{user_id}/media_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": token
    }

    print("[+] Publishing Reel to Instagram...")
    pub_resp = requests.post(publish_url, data=pub_payload, timeout=30)
    pub_data = pub_resp.json()

    if "id" not in pub_data:
        raise RuntimeError(f"Failed to publish Reel: {pub_data}")

    published_id = pub_data["id"]
    print(f"[OK] Reel successfully published live to Instagram! Media ID: {published_id}")

    return {
        "status": "PUBLISHED",
        "media_id": published_id
    }

if __name__ == "__main__":
    res = publish_reel_to_instagram("https://example.com/sample.mp4", "Test reel")
    print(res)
