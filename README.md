# 🧠 MindBridge

Mental health support web app for Indian college students.

## 📁 Structure
```
mindbridge/
├── backend/
│   ├── app.py           ← FastAPI (API + serves frontend)
│   ├── database.py      ← SQLite setup
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── checkin.html
│   ├── tracker.html
│   ├── chat.html
│   ├── community.html
│   ├── resources.html
│   └── api.js
├── render.yaml          ← Render auto-deploy config
└── .gitignore
```

---

## 💻 Run Locally

```bash
# 1. Install
pip install -r backend/requirements.txt

# 2. Run
uvicorn backend.app:app --reload --port 8000

# 3. Open
http://localhost:8000
```

> AI chat won't work locally without setting GROQ_API_KEY.
> Get free key at console.groq.com → paste in terminal:
> Windows CMD: `set GROQ_API_KEY=gsk_your_key`
> PowerShell:  `$env:GROQ_API_KEY="gsk_your_key"`

---

## 🚀 Deploy on Render (Step by Step)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "MindBridge initial commit"
# Create repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/mindbridge.git
git push -u origin main
```

### Step 2 — Create Render Account
Go to [render.com](https://render.com) → Sign up (free)

### Step 3 — New Web Service
- Click **New +** → **Web Service**
- Connect GitHub → select your `mindbridge` repo
- Render detects `render.yaml` automatically → click **Apply**

### Step 4 — Add GROQ API Key
- In your service → **Environment** tab
- Click **Add Environment Variable**
- Key: `GROQ_API_KEY` | Value: `gsk_your_key_here`
- Get free key: [console.groq.com](https://console.groq.com) → API Keys

### Step 5 — Add Persistent Disk (so DB survives deploys)
- Go to **Disks** tab → **Add Disk**
- Name: `mindbridge-db`
- Mount Path: `/data`
- Size: 1 GB (free)

### Step 6 — Deploy!
Click **Deploy** — wait ~2 mins → your app is live! 🎉

---

## 🔗 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Check server status |
| POST | `/api/mood` | Save mood check-in |
| GET | `/api/mood/{session_id}` | Get mood history |
| POST | `/api/chat` | Chat with AI |
| GET | `/api/community` | Get community posts |
| POST | `/api/community` | Create post |
| GET | `/docs` | Interactive API docs |
