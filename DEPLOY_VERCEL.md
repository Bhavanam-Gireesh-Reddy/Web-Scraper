# Deploying Scrape Studio to Vercel

Follow these steps to deploy **Scrape Studio** using **Vercel**, **MongoDB Atlas**, and **Vercel Blob**.

## 1. MongoDB Atlas (Database)

1.  Log in to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2.  Create a free **M0 Cluster**.
3.  Create a **Database User** (with read/write access).
4.  Configure **Network Access**:
    *   For Vercel dynamic IPs, you typically need to allow access from anywhere (`0.0.0.0/0`).
    *   *Tip*: Use the Atlas native Vercel integration for a more secure connection if preferred.
5.  Copy your **Connection String** (for Python). It looks like this:
    `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

## 2. Vercel Blob (PDF Storage)

Since Vercel has a read-only filesystem, generated PDFs must be stored in the cloud.

1.  In your **Vercel Dashboard**, go to **Storage**.
2.  Create a new **Blob** store.
3.  Connect it to your project.
4.  Vercel will automatically add `BLOB_READ_WRITE_TOKEN` to your environment.

## 3. Required Environment Variables

Go to **Project Settings > Environment Variables** and add:

| Key | Value |
| :--- | :--- |
| `GROQ_API_KEY` | Your key from [console.groq.com](https://console.groq.com) |
| `MONGODB_URI` | Your Atlas Connection String (from Step 1) |
| `MONGODB_DB` | `scrape_chat_app` |
| `MONGODB_COLLECTION` | `documents` |
| `PDF_STORAGE_BACKEND` | `vercel_blob` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |

## 4. Deployment Steps

1.  **Push to GitHub**: Commit all files (including the updated `vercel.json` and `requirements.txt`).
2.  **Import to Vercel**: Import your repository into the Vercel Dashboard.
3.  **Zero Configuration**: The included [vercel.json](./vercel.json) will automatically tell Vercel to use the Python runtime and route all traffic to `app.py`.
4.  **Deploy**: Click **Deploy** and wait for the "Congratulations" screen.

## 5. Important Notes

- **Static Fallback**: Browser-based scraping (`crawl4ai`) requires Playwright binaries which are too large for standard Vercel functions. The app will automatically fall back to its **Static Scraper** (using BeautifulSoup) in the cloud.
- **Cold Starts**: The first request after some time might be slow (1-2 seconds) while the Python function wakes up.
- **Persistent Data**: No local files will persist on Vercel. Ensure `PDF_STORAGE_BACKEND` is **NOT** set to `local` in production.
