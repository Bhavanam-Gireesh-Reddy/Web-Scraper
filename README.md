# Scrape Studio

Scrape Studio is a FastAPI web application that:

- scrapes website content
- generates a uniquely named PDF automatically
- stores document history in MongoDB
- lets users reopen previous scrapes from a history page
- provides a Groq-powered chatbot that answers only from the selected scraped document

This project is built to run both:

- locally with MongoDB and local PDF storage
- on Vercel with MongoDB Atlas and Vercel Blob storage

## Features

- Modern multi-page frontend with dashboard, history, and document workspace
- Website scraping with a lightweight static HTML crawler
- Optional browser-style crawling locally if `crawl4ai` is installed
- Automatic fallback scraper using `requests + BeautifulSoup` if the browser crawler fails
- Auto-generated PDF names based on domain + detected title + timestamp
- PDF generation from scraped content
- MongoDB document storage
- History page for previous scrapes
- Selected-document chatbot using Groq
- Strict document-only answering behavior to reduce hallucination
- Vercel-ready deployment support
- MongoDB Atlas-ready database support
- Vercel Blob support for storing generated PDFs in the cloud

## How It Works

1. A user enters a website URL.
2. The app scrapes content from the site.
3. The content is cleaned and combined.
4. A PDF is generated with a unique automatic name.
5. The document metadata and content are stored in MongoDB.
6. The user is redirected to a document workspace.
7. The chatbot shows which PDF is currently selected.
8. The chatbot answers only from the selected document and rejects unrelated questions.

## Tech Stack

- Backend: FastAPI
- Frontend: Jinja2 templates, vanilla JavaScript, CSS
- Database: MongoDB / MongoDB Atlas
- AI: Groq API
- Scraping: `requests`, `beautifulsoup4`
- Optional local browser scraping: `crawl4ai`
- PDF generation: `fpdf2`
- Cloud file storage on Vercel: Vercel Blob

## Project Structure

```text
Scraping/
├── app.py
├── scraper.py
├── requirements.txt
├── vercel.json
├── .env.example
├── README.md
├── DEPLOY_VERCEL.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── history.html
│   └── document.html
└── static/
    ├── css/
    │   └── styles.css
    ├── js/
    │   └── main.js
    └── pdfs/
```

## Main Pages

- `/`
  Dashboard page where the user starts a new scrape

- `/history`
  History page showing previously scraped documents

- `/documents/{document_id}`
  Document workspace for a specific scraped document, with PDF preview and chatbot

## API Routes

- `POST /api/scrape`
  Scrapes a URL, creates a PDF, stores the result, and returns the saved document

- `GET /api/documents`
  Returns recent saved documents

- `GET /api/documents/{document_id}`
  Returns a specific saved document

- `POST /api/chat`
  Sends a question to the chatbot for one selected document only

## Chatbot Behavior

The chatbot is intentionally strict.

- It only uses the selected document
- It shows which PDF is active before the user asks questions
- It includes the selected PDF name in the response payload
- It rejects unrelated questions
- It avoids outside knowledge as much as possible
- It uses relevant text chunks from the selected document instead of the full database

Fallback behavior:

```text
I can't answer that from the selected PDF: <pdf_name>.
```

## Environment Variables

Create a `.env` file based on `.env.example`.

### Required

- `GROQ_API_KEY`
- `MONGODB_URI`
- `MONGODB_DB`
- `MONGODB_COLLECTION`

### Recommended

- `GROQ_MODEL`
- `SCRAPE_MAX_PAGES`
- `PDF_STORAGE_BACKEND`

### Required For Vercel PDF Storage

- `BLOB_READ_WRITE_TOKEN`

## Example `.env`

```env
GROQ_API_KEY=your_groq_api_key_here
MONGODB_URI=mongodb+srv://username:password@cluster-name.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=ScrapeStudio
MONGODB_DB=scrape_chat_app
MONGODB_COLLECTION=documents
GROQ_MODEL=llama-3.3-70b-versatile
SCRAPE_MAX_PAGES=20
PDF_STORAGE_BACKEND=vercel_blob
BLOB_READ_WRITE_TOKEN=your_vercel_blob_token_here
```

## Local Development Setup

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create `.env`

Copy `.env.example` to `.env` and fill in your real values.

### 4. If using local MongoDB

Set:

```env
MONGODB_URI=mongodb://localhost:27017
PDF_STORAGE_BACKEND=local
```

### 5. Run the app

```powershell
uvicorn app:app --reload
```

### 6. Open the site

```text
http://127.0.0.1:8000
```

## MongoDB Atlas Setup

If you want to use MongoDB Atlas instead of local MongoDB:

1. Create an Atlas cluster
2. Create a database user
3. Copy the Python connection string
4. Put that value into `MONGODB_URI`

Example:

```env
MONGODB_URI=mongodb+srv://username:password@cluster-name.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=ScrapeStudio
```

### Atlas Network Access

For local development:

- add your current IP address to the Atlas network access list

For Vercel deployments:

- Vercel uses dynamic IP addresses
- the simplest option is usually allowing `0.0.0.0/0`
- or use the MongoDB Atlas native Vercel integration

Be careful with public IP allowlisting and use strong database credentials.

## Local vs Cloud PDF Storage

This project supports two PDF storage modes.

### Local mode

Use for local development.

```env
PDF_STORAGE_BACKEND=local
```

Behavior:

- PDFs are written to `static/pdfs/`
- PDF URLs look like `/static/pdfs/<file>.pdf`

### Vercel Blob mode

Use for Vercel deployment.

```env
PDF_STORAGE_BACKEND=vercel_blob
```

Behavior:

- PDFs are uploaded to Vercel Blob
- PDF URLs are stored as Blob URLs in MongoDB
- generated PDFs remain available after serverless execution ends

## Deploying to Vercel

This project is prepared for Vercel, but there is one important platform detail:

- runtime-generated files should not rely on local filesystem persistence

That is why Vercel Blob support is included.

### Recommended Vercel Setup

Use:

- MongoDB Atlas for database
- Vercel Blob for PDFs
- Groq API for chat

### Deployment Steps

1. Push the project to GitHub
2. Import the repo into Vercel
3. Add environment variables in Vercel Project Settings
4. Create a Vercel Blob store
5. Set `PDF_STORAGE_BACKEND=vercel_blob`
6. Deploy

### Environment Variables to Add in Vercel

- `GROQ_API_KEY`
- `MONGODB_URI`
- `MONGODB_DB`
- `MONGODB_COLLECTION`
- `GROQ_MODEL`
- `SCRAPE_MAX_PAGES`
- `PDF_STORAGE_BACKEND`
- `BLOB_READ_WRITE_TOKEN`

### Vercel Config

The project includes [vercel.json](C:/Users/hp/Downloads/Scraping/vercel.json) to:

- keep Vercel configuration simple for FastAPI auto-detection at the project root

## Notes About Vercel Deployment

- MongoDB Atlas is the correct choice for production deployment
- Vercel Blob is the correct choice for generated PDFs in production
- Vercel uses the lightweight static HTML scraper path to keep deployment size manageable
- if optional local `crawl4ai` / Playwright scraping fails, the app automatically falls back to a static HTML scraper
- very large sites may still take time and may hit serverless execution limits

## Current Default AI Model

The app currently defaults to:

```text
llama-3.3-70b-versatile
```

This replaced the older `llama3-8b-8192` default because that older model is no longer supported by Groq.

## Important Files

- [app.py](C:/Users/hp/Downloads/Scraping/app.py)
  Main FastAPI app, MongoDB connection, routes, chat logic, and PDF storage handling

- [scraper.py](C:/Users/hp/Downloads/Scraping/scraper.py)
  Scraping logic, fallback scraping, content cleaning, and PDF creation

- [templates/index.html](C:/Users/hp/Downloads/Scraping/templates/index.html)
  Dashboard page

- [templates/history.html](C:/Users/hp/Downloads/Scraping/templates/history.html)
  History page

- [templates/document.html](C:/Users/hp/Downloads/Scraping/templates/document.html)
  Document workspace with PDF preview and chatbot

- [static/css/styles.css](C:/Users/hp/Downloads/Scraping/static/css/styles.css)
  Main UI styling

- [static/js/main.js](C:/Users/hp/Downloads/Scraping/static/js/main.js)
  Frontend interaction logic

- [DEPLOY_VERCEL.md](C:/Users/hp/Downloads/Scraping/DEPLOY_VERCEL.md)
  Short Vercel deployment notes

## Common Problems

### 1. Scraper fails on Windows with Playwright / subprocess errors

The project already includes a fallback scraper.

If browser scraping fails:

- the app automatically switches to static HTML scraping

### 2. MongoDB connection fails

Check:

- `MONGODB_URI`
- Atlas user/password
- Atlas IP/network access list

### 3. Groq chat fails

Check:

- `GROQ_API_KEY`
- `GROQ_MODEL`
- Groq account access and rate limits

### 4. PDFs are not available after deployment

Check:

- `PDF_STORAGE_BACKEND=vercel_blob`
- `BLOB_READ_WRITE_TOKEN`

If you deploy to Vercel and keep local storage mode, generated PDFs will not be reliably persistent.

## Recommended Production Setup

- Hosting: Vercel
- Database: MongoDB Atlas
- PDF storage: Vercel Blob
- Chat model: Groq `llama-3.3-70b-versatile`

## Install Command Summary

```powershell
pip install -r requirements.txt
uvicorn app:app --reload
```

## Future Improvements

- Delete document from history
- Progress indicator for scraping / PDF / save stages
- Authentication for private user workspaces
- Better chunk ranking for large documents
- Background job queue for long scrapes
- Per-user document collections

## License

Add your preferred license here.
