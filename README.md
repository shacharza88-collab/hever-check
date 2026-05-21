# Hever Store Checker — Web App

Check if a store supports the חבר card (חבר שלי) from any browser, including mobile.

---

## Deploy to Render (free)

### 1. Push to GitHub
Create a new GitHub repo and push the `hever/` folder contents to it.  
Make sure `.env` is in `.gitignore` — don't upload your credentials.

### 2. Create Render Web Service
1. Go to [render.com](https://render.com) and sign up (free)
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — just click **Deploy**
5. Wait ~2 minutes → you get a URL like `https://hever-check.onrender.com`

Open that URL on your phone. Done.

---

## Keep it always awake (UptimeRobot)

Render free tier sleeps after 15 min of inactivity (slow first request).  
UptimeRobot pings it every 10 minutes to keep it awake — free.

### Setup (5 minutes)
1. Go to [uptimerobot.com](https://uptimerobot.com) and sign up (free)
2. Click **Add New Monitor**
3. Fill in:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Hever Check
   - **URL:** `https://hever-check.onrender.com/check?q=ACE`
   - **Monitoring Interval:** 5 minutes
4. Click **Create Monitor**

That's it — your app stays awake 24/7 at zero cost.

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask web app |
| `hever_lite.py` | Core search logic (no dependencies) |
| `hever_check.py` | Full version with login (local use only) |
| `requirements.txt` | Flask only |
| `render.yaml` | Render deploy config |
| `.env` | Your credentials — **never upload this** |
