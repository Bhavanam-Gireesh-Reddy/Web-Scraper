# Deploying Scrape Studio to Vercel

Follow these steps to deploy **Scrape Studio** using **Vercel**, **MongoDB Atlas**, and **Vercel Blob**.

## 1. MongoDB Atlas (Database)

1.  Log in to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2.  Use your cluster: `cluster0.ya1maim.mongodb.net`.
3.  Your username is: `gbhavanam69`.
4.  Copy your **Connection String**:
    `mongodb+srv://gbhavanam69:<db_password>@cluster0.ya1maim.mongodb.net/?appName=Cluster0`
    *Note: Replace `<db_password>` with your actual password.*
5.  Configure **Network Access**:
    *   Allow access from **anywhere** (`0.0.0.0/0`) so Vercel can reach it.

## 2. Vercel Blob (PDF Storage)

Since Vercel has a read-only filesystem, generated PDFs must be stored in the cloud.

1.  In your **Vercel Dashboard**, go to **Storage**.
2.  Create a new **Blob** store.
3.  Connect it to your project.
4.  Vercel will automatically add `BLOB_READ_WRITE_TOKEN`.

## 3. Required Environment Variables

Go to **Project Settings > Environment Variables** and add:

| Key | Value |
| :--- | :--- |
| `GROQ_API_KEY` | Your key from [console.groq.com](https://console.groq.com) |
| `MONGODB_URI` | `mongodb+srv://gbhavanam69:<db_password>@cluster0.ya1maim.mongodb.net/?appName=Cluster0` |
| `MONGODB_DB` | `scrape_chat_app` |
| `MONGODB_COLLECTION` | `documents` |
| `PDF_STORAGE_BACKEND` | `vercel_blob` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |

## 4. Deployment Steps

1.  **Push to GitHub**: Commit all files (including `vercel.json`).
2.  **Import to Vercel**: Import your repository.
3.  **Zero Configuration**: The included `vercel.json` handles everything.
4.  **Deploy**: Click **Deploy**.

## 5. Important Notes

- **Static Fallback**: The app will automatically switch to its **Static Scraper** on Vercel to stay within the platform's limits.
- **Cold Starts**: Initial request might take a few seconds after inactivity.
- **Persistent Data**: No local files will persist. Use Vercel Blob for PDFs.
