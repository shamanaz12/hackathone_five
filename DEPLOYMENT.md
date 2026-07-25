# 🚀 TaskFlow AI: Deployment Guide (Free Tier)

This guide provides a step-by-step process for deploying the TaskFlow AI Support Agent for free using **Render** (Backend & Database) and **Vercel** (Frontend Dashboard).

## 🏗️ 1. Backend & Database (Render)

We use Render's Blueprint feature for a one-click deployment of the FastAPI server and a PostgreSQL database.

1.  **Push your code to GitHub** (if not already done).
2.  Go to [Render Dashboard](https://dashboard.render.com/).
3.  Click **New +** -> **Blueprint**.
4.  Connect your GitHub repository: `https://github.com/shamanaz12/hackathone_five`.
5.  Render will automatically detect the `render.yaml` file and set up:
    *   **PostgreSQL Database** (Free Plan).
    *   **FastAPI Web Service**.
6.  **Configuration:** In the Render dashboard for the `taskflow-backend` service, go to **Environment** and add:
    *   `OPENAI_API_KEY`: Your OpenAI API Key.
    *   `CORS_ORIGINS`: `https://your-frontend.vercel.app,http://localhost:3000` (Update this once your frontend is deployed).

## 💻 2. Frontend Dashboard (Vercel)

Vercel is optimized for Next.js and offers a great free tier.

1.  Go to [Vercel Dashboard](https://vercel.com/).
2.  Click **Add New** -> **Project**.
3.  Import your GitHub repository: `shamanaz12/hackathone_five`.
4.  **Crucial Setting:** In the "Configure Project" screen:
    *   **Root Directory:** Set this to `support-web`.
5.  **Environment Variables:** Add the following:
    *   `NEXT_PUBLIC_API_URL`: The URL of your Render backend (e.g., `https://taskflow-backend.onrender.com`).
6.  Click **Deploy**.

## 🔄 3. Final Connection

1.  Once your Vercel frontend is deployed, copy its URL (e.g., `https://taskflow-ai.vercel.app`).
2.  Go back to **Render** -> **taskflow-backend** -> **Environment**.
3.  Update `CORS_ORIGINS` to include your Vercel URL.
4.  Your system is now fully live and connected!

---
*Generated for TaskFlow AI — 2026*
