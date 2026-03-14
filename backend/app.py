from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import random, pathlib, httpx, uvicorn, os

from database import get_db, init_db

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG  ← API key is read from environment variable (never hardcoded)
#           Set GROQ_API_KEY in Render Dashboard → Environment
# ══════════════════════════════════════════════════════════════════════════════
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL   = "compound-beta"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are MindBridge, a warm and empathetic mental health support companion for Indian college students.

PERSONALITY:
- Talk like a caring, trusted friend — never robotic or clinical
- Use simple natural language with occasional emojis (💚💙😊)
- Always validate feelings first, then ask one thoughtful follow-up question
- Keep replies short — 3 to 5 sentences max

MEMORY:
- Remember the user's name if they share it and use it naturally
- Remember their mood, problems, and situation throughout the conversation
- Refer back to earlier things they said

TOPICS:
- Exam stress, family pressure, loneliness, career confusion
- Relationship issues, anxiety, sleep problems, general mood

RULES:
- Never diagnose or prescribe medication
- For suicide/self-harm → always refer to iCall: 9152987821
- Never give generic responses — always respond to what the person actually said
- You are a support tool, not a replacement for professional mental health care

TONE: Friendly, supportive, calm, encouraging.
Always focus on helping students feel heard, understood, and supported."""

_chat_history: dict[str, list[dict]] = {}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="MindBridge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    key_status = "✅ Set" if GROQ_API_KEY else "❌ MISSING — set GROQ_API_KEY env var!"
    print(f"✅ MindBridge started! | Groq Key: {key_status}")

FRONTEND = pathlib.Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND / "index.html"))

@app.get("/{page}.html")
def serve_page(page: str):
    fp = FRONTEND / f"{page}.html"
    if fp.exists():
        return FileResponse(str(fp))
    raise HTTPException(404, "Page not found")


# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════
class MoodEntry(BaseModel):
    session_id: str
    mood: int
    label: str
    emoji: str
    note: Optional[str] = ""

class ChatMessage(BaseModel):
    session_id: str
    message: str

class CommunityPost(BaseModel):
    session_id: str
    content: str
    tag: Optional[str] = "General"

class PostVote(BaseModel):
    session_id: str


# ══════════════════════════════════════════════════════════════════════════════
# MOOD ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/mood")
def save_mood(entry: MoodEntry):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO moods (session_id, mood, label, emoji, note, created_at) VALUES (?,?,?,?,?,?)",
            (entry.session_id, entry.mood, entry.label, entry.emoji, entry.note, datetime.now().isoformat())
        )
        db.commit()
        rows = db.execute(
            "SELECT created_at FROM moods WHERE session_id=? ORDER BY created_at DESC",
            (entry.session_id,)
        ).fetchall()
        return {"success": True, "streak": _calc_streak(rows), "message": "Mood saved!"}
    finally:
        db.close()

@app.get("/api/mood/{session_id}")
def get_moods(session_id: str, days: int = 30):
    db = get_db()
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = db.execute(
            "SELECT mood, label, emoji, note, created_at FROM moods WHERE session_id=? AND created_at>=? ORDER BY created_at DESC",
            (session_id, since)
        ).fetchall()
        moods = [{"mood": r[0], "label": r[1], "emoji": r[2], "note": r[3], "date": r[4]} for r in rows]
        avg    = sum(m["mood"] for m in moods) / len(moods) if moods else 0
        streak = _calc_streak(db.execute(
            "SELECT created_at FROM moods WHERE session_id=? ORDER BY created_at DESC",
            (session_id,)
        ).fetchall()) if moods else 0
        return {"moods": moods, "avg": round(avg, 1), "streak": streak, "total": len(moods)}
    finally:
        db.close()

@app.get("/api/mood/stats/global")
def global_stats():
    db = get_db()
    try:
        total = db.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
        avg   = db.execute("SELECT AVG(mood) FROM moods").fetchone()[0] or 0
        users = db.execute("SELECT COUNT(DISTINCT session_id) FROM moods").fetchone()[0]
        return {"total_checkins": total, "avg_mood": round(avg, 1), "total_users": users}
    finally:
        db.close()

def _calc_streak(rows):
    if not rows:
        return 0
    dates = sorted(set(r[0][:10] for r in rows), reverse=True)
    streak, today = 0, datetime.now().date()
    for i, d in enumerate(dates):
        if d == (today - timedelta(days=i)).isoformat():
            streak += 1
        else:
            break
    return streak


# ══════════════════════════════════════════════════════════════════════════════
# GROQ AI
# ══════════════════════════════════════════════════════════════════════════════
CRISIS_WORDS = [
    "suicide", "kill myself", "end it", "don't want to live", "want to die",
    "no reason to live", "hopeless", "self harm", "hurt myself",
    "give up on life", "not worth living", "end my life"
]

CRISIS_RESPONSE = (
    "I really hear what you're saying, and I'm very glad you told me. 💙\n\n"
    "What you're feeling is real — and you deserve real support right now.\n\n"
    "🚨 Please reach out to iCall: 9152987821 — it's free, confidential, and available today.\n\n"
    "You don't have to face this alone. Will you make that call?"
)

FALLBACK_RESPONSES = [
    "I hear you 💚 Can you tell me a little more about what's going on?",
    "I'm here with you. What's been the hardest part of your day?",
    "Thank you for sharing that. Whatever you're feeling right now is valid. 💙",
    "You don't have to go through this alone — I'm listening. What's on your mind?",
]

def ask_groq(session_id: str, user_message: str) -> Optional[str]:
    if not GROQ_API_KEY:
        print("⚠️  GROQ_API_KEY not set — using fallback response")
        return None
    if session_id not in _chat_history:
        _chat_history[session_id] = []
    _chat_history[session_id].append({"role": "user", "content": user_message})
    history  = _chat_history[session_id][-20:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    try:
        r = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages, "max_tokens": 300, "temperature": 0.75},
            timeout=15,
        )
        data = r.json()
        if r.status_code != 200:
            print(f"❌ GROQ ERROR {r.status_code}: {data.get('error', {})}")
            return None
        reply = data["choices"][0]["message"]["content"].strip()
        _chat_history[session_id].append({"role": "assistant", "content": reply})
        return reply
    except httpx.TimeoutException:
        print("⚠️  Groq timed out")
        return None
    except Exception as e:
        print(f"⚠️  Groq exception: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CHAT ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/chat")
def chat(msg: ChatMessage):
    db = get_db()
    try:
        if any(w in msg.message.lower() for w in CRISIS_WORDS):
            response, is_crisis = CRISIS_RESPONSE, True
        else:
            reply     = ask_groq(msg.session_id, msg.message)
            response  = reply if reply else random.choice(FALLBACK_RESPONSES)
            is_crisis = False
        now = datetime.now().isoformat()
        db.execute("INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (msg.session_id, "user", msg.message, now))
        db.execute("INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (msg.session_id, "ai", response, now))
        db.commit()
        return {"response": response, "is_crisis": is_crisis}
    finally:
        db.close()

@app.get("/api/chat/history/{session_id}")
def get_chat_history(session_id: str, limit: int = 50):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return {"messages": [{"role": r[0], "content": r[1], "time": r[2]} for r in rows]}
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/community")
def create_post(post: CommunityPost):
    if len(post.content.strip()) < 5:
        raise HTTPException(400, "Post too short")
    if len(post.content) > 500:
        raise HTTPException(400, "Post too long")
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO community_posts (session_id, content, tag, upvotes, created_at) VALUES (?,?,?,0,?)",
            (post.session_id, post.content.strip(), post.tag, datetime.now().isoformat())
        )
        db.commit()
        return {"success": True, "post_id": cur.lastrowid}
    finally:
        db.close()

@app.get("/api/community")
def get_posts(limit: int = 30, tag: Optional[str] = None):
    db = get_db()
    try:
        if tag and tag != "All":
            rows = db.execute(
                "SELECT id, content, tag, upvotes, created_at FROM community_posts WHERE tag=? ORDER BY created_at DESC LIMIT ?",
                (tag, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, content, tag, upvotes, created_at FROM community_posts ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return {"posts": [{"id": r[0], "content": r[1], "tag": r[2], "upvotes": r[3], "date": r[4]} for r in rows]}
    finally:
        db.close()

@app.post("/api/community/{post_id}/upvote")
def upvote_post(post_id: int, vote: PostVote):
    db = get_db()
    try:
        if db.execute("SELECT id FROM post_votes WHERE post_id=? AND session_id=?",
                      (post_id, vote.session_id)).fetchone():
            return {"success": False, "message": "Already voted"}
        db.execute("UPDATE community_posts SET upvotes=upvotes+1 WHERE id=?", (post_id,))
        db.execute("INSERT INTO post_votes (post_id, session_id) VALUES (?,?)", (post_id, vote.session_id))
        db.commit()
        new_count = db.execute("SELECT upvotes FROM community_posts WHERE id=?", (post_id,)).fetchone()[0]
        return {"success": True, "upvotes": new_count}
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    db = get_db()
    try:
        moods = db.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
        posts = db.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
        chats = db.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        return {
            "status": "healthy",
            "db": "connected",
            "ai": f"Groq compound-beta ({'key set ✅' if GROQ_API_KEY else 'NO KEY ❌'})",
            "stats": {"moods": moods, "posts": posts, "chat_messages": chats}
        }
    finally:
        db.close()


# ── Local run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
