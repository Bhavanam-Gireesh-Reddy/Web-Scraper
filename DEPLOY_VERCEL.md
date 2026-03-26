# Deploying Scrape Studio to Vercel with MongoDB Atlas

## 1. MongoDB Atlas

1. Create an Atlas cluster.
2. Create a database user.
3. Copy the Python connection string from Atlas.
4. Allow Vercel access.
   - If you use the Vercel native Atlas integration, Vercel can set `MONGODB_URI` for you.
   - If you connect manually, Atlas must allow Vercel's dynamic IP usage. For simple public deployment, this usually means allowing `0.0.0.0/0`.

## 2. Vercel Blob

Generated PDFs cannot rely on Vercel's local filesystem if you want them to remain available after the request finishes. This app supports Vercel Blob for PDF storage.

1. In your Vercel project, create a Blob store.
2. Add `BLOB_READ_WRITE_TOKEN` to the project environment variables.
3. Set `PDF_STORAGE_BACKEND=vercel_blob`.

## 3. Required Environment Variables

Add these in Vercel Project Settings -> Environment Variables:

- `GROQ_API_KEY`
- `MONGODB_URI`
- `MONGODB_DB`
- `MONGODB_COLLECTION`
- `GROQ_MODEL`
- `SCRAPE_MAX_PAGES`
- `PDF_STORAGE_BACKEND`
- `BLOB_READ_WRITE_TOKEN`

## 4. Deploy

1. Push this project to GitHub.
2. Import the repo into Vercel.
3. Keep the project root as this folder.
4. Let Vercel auto-detect the FastAPI app from `app.py`.
5. Let Vercel install from `requirements.txt`.
6. Deploy.

## 5. Notes

- The app uses MongoDB Atlas by connection string, so no code change is needed when switching from local MongoDB to Atlas.
- The app stores PDF URLs in MongoDB. On Vercel, these should be Blob URLs, not local file paths.
- Vercel uses the lightweight static HTML scraper path to avoid oversized serverless dependencies.
- If you want browser-style crawling locally, you can install `crawl4ai` in your local environment without adding it to Vercel deployment dependencies.
