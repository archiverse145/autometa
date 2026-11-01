import os
import requests
import json
from config import IG_ACCESS_TOKEN, IG_USERNAME, IG_PASSWORD
from database import get_db, log_reel_insights, get_top_performing_reels

def sync_instagram_insights(access_token: str = None) -> list:
    """
    Pulls real-time analytics (plays, likes, comments) from Instagram
    for all published reels and updates the database.
    """
    token = access_token or IG_ACCESS_TOKEN or os.getenv("IG_ACCESS_TOKEN", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ig_media_id FROM reels WHERE status = 'PUBLISHED' AND ig_media_id IS NOT NULL")
    reels = cursor.fetchall()

    cl = None
    if not token and IG_USERNAME and IG_PASSWORD:
        try:
            from ig_direct_publisher import get_instagram_client
            cl = get_instagram_client(IG_USERNAME, IG_PASSWORD)
        except Exception as e:
            print(f"[!] Could not connect to pull direct stats: {e}")

    updated = []
    for r in reels:
        reel_id = r["id"]
        media_id = str(r["ig_media_id"])

        if "simulated" in media_id:
            continue

        if cl and media_id.isdigit():
            try:
                info = cl.media_info(int(media_id))
                views = getattr(info, "play_count", 0) or getattr(info, "view_count", 0) or 0
                likes = getattr(info, "like_count", 0) or 0
                comments = getattr(info, "comment_count", 0) or 0
                log_reel_insights(reel_id, views, likes, comments, shares=0, saves=0)
                updated.append({"reel_id": reel_id, "views": views, "likes": likes})
                print(f"[+] Reel #{reel_id} updated: {views} views, {likes} likes, {comments} comments")
                continue
            except Exception as e:
                print(f"[!] Error fetching direct insights for #{reel_id}: {e}")

        if not token:
            continue

        try:
            url = f"https://graph.facebook.com/v19.0/{media_id}/insights"
            params = {
                "metric": "plays,reach,saved,shares,likes,comments",
                "access_token": token
            }
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json().get("data", [])

            metrics = {item["name"]: item["values"][0]["value"] for item in data if "values" in item}
            views = metrics.get("plays", 0) or metrics.get("reach", 0)
            likes = metrics.get("likes", 0)
            comments = metrics.get("comments", 0)
            shares = metrics.get("shares", 0)
            saves = metrics.get("saved", 0)

            log_reel_insights(reel_id, views, likes, comments, shares, saves)
            updated.append({"reel_id": reel_id, "views": views, "shares": shares})
            print(f"[+] Reel #{reel_id} updated: {views} views, {shares} shares, {saves} saves")
        except Exception as e:
            print(f"[!] Error fetching insights for reel #{reel_id}: {e}")

    if cl:
        try:
            cl.session.close()
        except Exception:
            pass

    conn.close()
    return updated

def analyze_audience_preferences() -> str:
    """
    Evaluates top-performing reels from the database to extract what topics and styles the audience wants.
    Returns a prompt instruction string to guide future script generations.
    """
    top_reels = get_top_performing_reels(limit=5)
    if not top_reels or not any(r.get("total_views") for r in top_reels):
        return "Focus on fast, curiosity-driven hooks with high contrast visual keywords."

    summary = "Audience Preferences based on actual performance data:\n"
    for r in top_reels:
        summary += f"- Topic: '{r['topic']}' | Keywords: {r['keywords']} | Views: {r['total_views']} | Shares: {r['total_shares']}\n"

    summary += "\nGuidance for next generation: Double down on themes and keywords similar to the top-shared topics above."
    return summary

if __name__ == "__main__":
    sync_instagram_insights()
    analysis = analyze_audience_preferences()
    print("\n--- Strategy Directive for Next Generation ---")
    print(analysis)
