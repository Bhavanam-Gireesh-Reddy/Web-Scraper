# 🚀 Deploying Scrape Studio to Render

I have optimized this project for Render. Follow these steps to get your app live with **Browser-based scraping** enabled!

## 📋 Prerequisites
1.  **Render Account:** Create one at [render.com](https://render.com).
2.  **GitHub Repo:** Ensure your code is pushed to your GitHub repository (I'll do this for you next!).

## 🛠️ Step-by-Step Deployment

1.  **New Blueprint:** Go to [Dashboard](https://dashboard.render.com), click **"New +"** and select **"Blueprint"**.
2.  **Connect Repo:** Connect your **Scrape Studio** repository.
3.  **Approve:** Render will read your `render.yaml` automatically. Review the plan (it will be "Free") and click **"Approve"**.
4.  **Set Environment Variables:**
    *   During setup, you will be asked for the following keys:
        *   `MONGODB_URI`: Your Atlas connection string (Standard format recommended).
        *   `GROQ_API_KEY`: Your Groq API key.
    *   *Note: Other variables like `SCRAPE_MAX_PAGES` are pre-filled for you.*

## ⚙️ Why Render is Better for this App
- **High Timeouts:** Unlike Vercel's 10s limit, Render lets your scrapes run until completion.
- **Full Browser Engine:** The build command automatically runs `playwright install chromium`, giving you the highest quality scraping possible with `crawl4ai`.
- **Production Server:** We use `gunicorn` to ensure the app stays alive and stable.

---

### Need Help?
If you see any errors in the **"Logs"** section on Render, just copy the last few lines and let me know!
