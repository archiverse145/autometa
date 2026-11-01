import sqlite3
from datetime import datetime
from config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,
        script TEXT,
        keywords TEXT,
        video_path TEXT,
        ig_caption TEXT,
        ig_media_id TEXT,
        status TEXT DEFAULT 'RENDERED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        published_at TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reel_id INTEGER,
        views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        saves INTEGER DEFAULT 0,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reel_id) REFERENCES reels (id)
    )
    """)
    conn.commit()
    conn.close()

def save_rendered_reel(topic: str, script: str, keywords: list[str], video_path: str, caption: str) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO reels (topic, script, keywords, video_path, ig_caption, status)
    VALUES (?, ?, ?, ?, ?, 'RENDERED')
    """, (topic, script, ",".join(keywords), str(video_path), caption))
    reel_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reel_id

def mark_reel_published(reel_id: int, ig_media_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE reels 
    SET ig_media_id = ?, status = 'PUBLISHED', published_at = ?
    WHERE id = ?
    """, (ig_media_id, datetime.utcnow().isoformat(), reel_id))
    conn.commit()
    conn.close()

def log_reel_insights(reel_id: int, views: int, likes: int, comments: int, shares: int, saves: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO insights (reel_id, views, likes, comments, shares, saves)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (reel_id, views, likes, comments, shares, saves))
    conn.commit()
    conn.close()

def get_top_performing_reels(limit: int = 5):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.id, r.topic, r.script, r.keywords, 
           MAX(i.views) as total_views, 
           MAX(i.likes) as total_likes,
           MAX(i.shares) as total_shares,
           MAX(i.saves) as total_saves
    FROM reels r
    LEFT JOIN insights i ON r.id = i.reel_id
    WHERE r.status = 'PUBLISHED'
    GROUP BY r.id
    ORDER BY total_views DESC, total_shares DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    init_db()
    print("[OK] Database initialized.")
