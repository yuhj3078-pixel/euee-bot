# EUEE Abebe Bot 🇪🇹

A powerful, AI-driven Telegram bot designed to help Ethiopian students prepare for the EUEE (Ethiopian University Entrance Examination). Built with FastAPI, Supabase, and multiple AI providers (Gemini, Groq, Anthropic).

## 🚀 Features

- **AI Tutor (Abebe):** Socratic-style tutoring using a friendly Ethiopian persona.
- **Subject Mastery:** Practice questions for 11 subjects (Math, Physics, Biology, etc.).
- **Study Notes & Audio:** Premium AI-generated study notes and audio lessons.
- **Mock Exams:** Real-time exam simulation with score prediction.
- **Weakness Radar:** AI-powered analysis of your weak topics.
- **Parent Dashboard:** Shareable links for parents to track progress.
- **National Leaderboard:** Compete with students across Ethiopia.
- **Automated Payments:** Integrated with Chapa for instant upgrades.

## 🛠️ Tech Stack

- **Backend:** Python (FastAPI + python-telegram-bot)
- **Database:** Supabase (PostgreSQL + RLS)
- **AI Models:** Gemini 1.5 Flash, Llama 3.3 (Groq), Claude 3.5 Sonnet.
- **Deployment:** Railway (Webhooks mode).
- **Rate Limiting:** Redis.

## 📦 Deployment Guide

### 1. Prerequisites
- A **GitHub** account.
- A **Railway** account.
- A **Supabase** project.
- A **Telegram Bot Token** (from @BotFather).

### 2. Database Setup
1. Go to your Supabase Dashboard → SQL Editor.
2. Run `supabase_schema.sql`.
3. Run `fix_payment_schema.sql` to normalize `payment_attempts` and backfill compatibility columns.
4. Run `supabase_security_hardening.sql` to enable RLS.
5. Do not run `final_supabase_schema.sql` on top of a database that already used `supabase_schema.sql`.

### 3. GitHub Push
1. Initialize git in your project: `git init`
2. Add all files: `git add .`
3. Commit: `git commit -m "Production ready"`
4. Push to a **Private** GitHub repository. **Never commit your `.env` file.**

### 4. Railway Deployment
1. Create a new project on Railway and "Deploy from GitHub repo".
2. Select your private `euee-bot` repository.
3. Add a **Redis** service to your project (for rate limiting).
4. Add the following **Environment Variables**:

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Your Telegram Bot Token |
| `ADMIN_USER_ID` | Your Telegram ID (to receive notifications) |
| `ADMIN_TOKEN` | A strong random string for admin dashboard login |
| `WEBHOOK_URL` | Your Railway App URL (e.g., `https://your-app.up.railway.app`) |
| `WEBHOOK_SECRET` | A strong random string (12+ chars) for Telegram security |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase Project URL |
| `SUPABASE_SERVICE_ROLE_KEY`| Your Supabase Service Role Key (bypasses RLS) |
| `DATABASE_URL` | Your Supabase Connection String (Transaction pooler preferred) |
| `CHAPA_SECRET_KEY` | Your Chapa Live/Test Secret Key |
| `BASE_WEB_URL` | Same as `WEBHOOK_URL` |
| `TELEBIRR_NUMBER` | The phone number for manual payments |
| `GEMINI_API_KEY` | Google AI Studio Key (Primary) |
| `GROQ_API_KEY` | Groq Key (Secondary) |
| `ANTHROPIC_API_KEY` | Anthropic Key (Optional) |
| `REDIS_URL` | Provided by Railway Redis service (automatic) |

### 5. Final Activation
- Once deployed, the bot will automatically register its webhook with Telegram.
- Send `/start` to your bot to begin.

## 🛡️ Security
- **RLS Enabled:** All database tables are protected by Row Level Security.
- **Webhook Validation:** All Telegram and Chapa callbacks are verified using HMAC signatures.
- **Admin Isolation:** Admin endpoints are protected by `httpOnly` cookies and strong tokens.
- **Rate Limiting:** IP-based rate limiting prevents brute-force attacks on the admin panel.

## ⚖️ License
Proprietary. All rights reserved.
