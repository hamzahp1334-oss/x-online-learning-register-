# 🚀 Deployment Guide: Online Quran Academy System

This guide explains how to deploy the **Online Quran Academy** system (Web Application + Dual Telegram Bots + Admin Panel + Database) to **Render** and **GitHub**.

---

## 📋 Overview

The system includes:
1. **Web Application & Admin Dashboard**: Flask / Waitress web app serving student registration, course catalogs, admin portal, and REST API.
2. **Student Telegram Bot (`@xmzgebabot`)**: Clean course browsing, Kitab catalogs, multi-language support (English, Amharic, Oromic, Arabic), step-by-step registration wizard, tuition instructions, and receipt upload.
3. **Admin Telegram Bot (`@xmzgebaadminbot`)**: Real-time admin alerts with receipt images, 1-click approvals, Kitab catalog management, teacher assignments, and schedule tracking.
4. **Google Sheets Sync & Background Scheduler**: Queues and synchronizes registrations to Google Sheets and dispatches class reminders.

`start.py` runs **both the Web Application and the Telegram Bots concurrently** in a single Render service.

---

## 🌐 Deploying to Render (Recommended)

### Step 1: Create a GitHub Repository
1. Initialize or upload this folder to a GitHub repository (e.g. `quran-academy`).
2. Make sure `.env` is NOT committed (use `.gitignore`). The tokens will be set as environment variables on Render.

### Step 2: Create a Web Service on Render
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** ➔ **Web Service**.
3. Connect your GitHub repository.
4. Set the following configuration settings:
   - **Name**: `quran-academy`
   - **Region**: Closest to your users (e.g. Frankfurt or Oregon)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install --upgrade pip && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     python start.py
     ```
   - **Plan**: `Free` (or Starter for persistent disks)

### Step 3: Add Environment Variables
Under the **Environment** tab on Render, add:

| Key | Value | Notes |
|---|---|---|
| `STUDENT_BOT_TOKEN` | `8594518638:AAFxCnlFmhNZhwc-tLKA1rjWBhIaAhoeHe8` | Student Bot token (@xmzgebabot) |
| `ADMIN_BOT_TOKEN` | `8914345551:AAG6RMn_og0u1srXZ53z-RIuwAx5UaHvdBM` | Admin Bot token (@xmzgebaadminbot) |
| `PORT` | `10000` | Port automatically assigned by Render |
| `HOST` | `0.0.0.0` | Listen on all interfaces |
| `ADMIN_EMAIL` | `admin@academy.test` | Initial Admin login email |
| `ADMIN_PASSWORD` | `adminpass12345` | Initial Admin login password |
| `ADMIN_NAME` | `Administrator` | Admin display name |
| `PYTHONUNBUFFERED` | `1` | Stream console logs in real time |

### Step 4: Deploy & Verify
1. Click **Deploy Web Service**.
2. Render will build the environment, install packages, and execute `python start.py`.
3. In the logs, verify:
   ```
   Both Student Bot and Admin Bot are live and polling updates!
   Serving Online Quran Academy web app on http://0.0.0.0:10000
   ```
4. Render's health check will hit `/health` and report **Service is live**!
5. Open your live Render URL (e.g. `https://quran-academy.onrender.com`) to view the website, and test the bots on Telegram!

---

## 🐳 Docker Deployment (Alternative)

To run with Docker:
```bash
docker compose up -d --build
```
The web service is available at `http://localhost:3000`, and the bots poll Telegram immediately.

---

## 🛠️ CLI Runner Modes

You can run individual services if desired:

```bash
# 1. Unified Mode (Web + Bots together — default):
python start.py

# 2. Telegram Bots only:
python start.py --bot-only
# or
python run_bot.py

# 3. Web Application only:
python start.py --web-only
# or
python app.py
```
