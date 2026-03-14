import sqlite3, pathlib, os

# Locally  → DB sits in backend/ folder
# On Render → Set DATA_DIR=/data (persistent disk), DB goes to /data/mindbridge.db
_data_dir = os.environ.get("DATA_DIR", str(pathlib.Path(__file__).parent))
DB_PATH   = pathlib.Path(_data_dir) / "mindbridge.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS moods (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            mood        INTEGER NOT NULL CHECK(mood BETWEEN 1 AND 5),
            label       TEXT    NOT NULL,
            emoji       TEXT    NOT NULL,
            note        TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('user','ai')),
            content     TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS community_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            tag         TEXT    DEFAULT 'General',
            upvotes     INTEGER DEFAULT 0,
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS post_votes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     INTEGER NOT NULL,
            session_id  TEXT    NOT NULL,
            UNIQUE(post_id, session_id)
        );
        CREATE INDEX IF NOT EXISTS idx_moods_session ON moods(session_id);
        CREATE INDEX IF NOT EXISTS idx_chat_session  ON chat_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_posts_created ON community_posts(created_at DESC);
    """)
    db.commit()
    db.close()
    print(f"✅ Database ready at {DB_PATH}")
