import asyncio
import datetime as dt
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from scraper import pdf_bytes_from_pages, scrape_website

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PDF_DIR = STATIC_DIR / "pdfs"
TEMPLATES_DIR = BASE_DIR / "templates"

STATIC_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "scrape_chat_app")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "documents")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SCRAPE_MAX_PAGES = int(os.getenv("SCRAPE_MAX_PAGES", "20"))

app = FastAPI(title="Scrape Studio")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ScrapeRequest(BaseModel):
    url: str = Field(..., min_length=8)


class ChatRequest(BaseModel):
    document_id: str
    message: str = Field(..., min_length=2)


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "please",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-")


def excerpt_text(text: str, limit: int = 240) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def extract_best_title(pages: list[dict[str, str]], fallback_url: str) -> str:
    for page in pages:
        for line in page["content"].splitlines():
            candidate = line.strip().lstrip("#").strip()
            if len(candidate) >= 5:
                return candidate
    parsed = urlparse(fallback_url)
    if parsed.path.strip("/"):
        return parsed.path.strip("/").split("/")[-1].replace("-", " ").title()
    return parsed.netloc.replace("www.", "")


def generate_auto_name(url: str, pages: list[dict[str, str]]) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "") or "scrape"
    title = extract_best_title(pages, url)
    readable = slugify(f"{domain} {title}")[:64] or slugify(domain) or "scrape"
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{readable}_{stamp}_{suffix}"


def serialize_document(doc: dict[str, Any], include_content: bool = False) -> dict[str, Any]:
    created_at = doc.get("created_at")
    if isinstance(created_at, dt.datetime):
        created_at_display = created_at.strftime("%d %b %Y, %I:%M %p")
        created_at_iso = created_at.isoformat()
    else:
        created_at_display = str(created_at or "")
        created_at_iso = str(created_at or "")

    payload = {
        "id": str(doc["_id"]),
        "url": doc.get("url", ""),
        "domain": doc.get("domain", ""),
        "title": doc.get("title", doc.get("auto_name", "Untitled")),
        "auto_name": doc.get("auto_name", "Untitled"),
        "pdf_path": doc.get("pdf_path", ""),
        "pdf_filename": doc.get("pdf_filename", ""),
        "pdf_storage": doc.get("pdf_storage", "local"),
        "page_count": doc.get("page_count", 0),
        "char_count": doc.get("char_count", 0),
        "created_at": created_at_iso,
        "created_at_display": created_at_display,
        "content_preview": doc.get("content_preview", ""),
        "pages": [
            {
                "url": page.get("url", ""),
                "preview": excerpt_text(page.get("content", ""), 700),
            }
            for page in doc.get("pages", [])[:8]
        ],
    }
    if include_content:
        payload["content"] = doc.get("content", "")
    return payload


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Document not found.")
    return ObjectId(value)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_chunks(pages: list[dict[str, str]], chunk_size: int = 1500, overlap: int = 250) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for page in pages:
        text = page.get("content", "").strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            chunk_text = text[start : start + chunk_size].strip()
            if chunk_text:
                chunks.append({"url": page.get("url", ""), "content": chunk_text})
            if start + chunk_size >= len(text):
                break
            start += chunk_size - overlap
    return chunks


def select_relevant_chunks(pages: list[dict[str, str]], question: str, limit: int = 5) -> list[dict[str, str]]:
    chunks = build_chunks(pages)
    if not chunks:
        return []

    query_tokens = [token for token in tokenize(question) if token not in STOP_WORDS]
    if not query_tokens:
        return chunks[:limit]

    scored: list[tuple[int, int, dict[str, str]]] = []
    question_lower = question.lower()
    unique_tokens = set(query_tokens)

    for index, chunk in enumerate(chunks):
        haystack = chunk["content"].lower()
        score = 0
        for token in unique_tokens:
            hits = haystack.count(token)
            if hits:
                score += hits * 3 + 1
        if question_lower in haystack:
            score += 8
        if score:
            scored.append((score, index, chunk))

    if not scored:
        return chunks[:limit]

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [item[2] for item in scored[:limit]]

    first_chunk = chunks[0]
    if first_chunk not in selected and len(selected) < limit:
        selected.insert(0, first_chunk)
    return selected[:limit]


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Groq API key not found. Add GROQ_API_KEY to your .env file.",
        )
    return Groq(api_key=api_key)


async def store_pdf_asset(pdf_filename: str, pdf_bytes: bytes) -> dict[str, str]:
    pdf_output_path = PDF_DIR / pdf_filename
    pdf_output_path.write_bytes(pdf_bytes)
    return {
        "pdf_path": f"/static/pdfs/{pdf_filename}",
        "pdf_filename": pdf_filename,
        "pdf_storage": "local",
    }


@app.on_event("startup")
async def startup_event() -> None:
    await initialize_mongo_state()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    mongo_client = getattr(app.state, "mongo_client", None)
    if mongo_client is not None:
        mongo_client.close()


async def initialize_mongo_state() -> None:
    if getattr(app.state, "mongo_client", None) is None:
        app.state.mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        app.state.database = app.state.mongo_client[MONGODB_DB]
        app.state.collection = app.state.database[MONGODB_COLLECTION]
        app.state.mongo_startup_error = ""

    try:
        await app.state.collection.create_index("created_at")
        await app.state.collection.create_index("url")
    except Exception as exc:
        app.state.mongo_startup_error = str(exc)


async def get_collection() -> Any:
    try:
        if getattr(app.state, "mongo_client", None) is None:
            await initialize_mongo_state()
        await app.state.mongo_client.admin.command("ping")
        return app.state.collection
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MongoDB is not reachable. Check MONGODB_URI. Details: {exc}",
        ) from exc


async def load_recent_documents(limit: int = 6) -> list[dict[str, Any]]:
    collection = await get_collection()
    rows = await collection.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [serialize_document(row) for row in rows]


async def load_document_counts() -> dict[str, int]:
    collection = await get_collection()
    total_documents = await collection.count_documents({})
    latest = await collection.find_one(sort=[("created_at", -1)])
    return {
        "total_documents": total_documents,
        "total_pages": latest.get("page_count", 0) if latest else 0,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    database_error = ""
    recent_documents: list[dict[str, Any]] = []
    stats = {"total_documents": 0, "total_pages": 0}

    try:
        recent_documents = await load_recent_documents(limit=6)
        stats = await load_document_counts()
    except HTTPException as exc:
        database_error = exc.detail

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recent_documents": recent_documents,
            "stats": stats,
            "database_error": database_error,
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    database_error = ""
    documents: list[dict[str, Any]] = []

    try:
        collection = await get_collection()
        rows = await collection.find().sort("created_at", -1).to_list(length=200)
        documents = [serialize_document(row) for row in rows]
    except HTTPException as exc:
        database_error = exc.detail

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "documents": documents,
            "database_error": database_error,
        },
    )


@app.get("/documents/{document_id}", response_class=HTMLResponse)
async def document_page(request: Request, document_id: str) -> HTMLResponse:
    collection = await get_collection()
    row = await collection.find_one({"_id": parse_object_id(document_id)})
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    document = serialize_document(row, include_content=True)
    return templates.TemplateResponse(
        "document.html",
        {
            "request": request,
            "document": document,
            "database_error": "",
        },
    )


@app.get("/api/documents")
async def get_history(limit: int = 25) -> list[dict[str, Any]]:
    collection = await get_collection()
    rows = await collection.find().sort("created_at", -1).limit(limit).to_list(limit)
    return [serialize_document(row) for row in rows]


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str) -> dict[str, Any]:
    collection = await get_collection()
    row = await collection.find_one({"_id": parse_object_id(document_id)})
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    return serialize_document(row, include_content=True)


@app.post("/api/scrape")
async def perform_scrape(req: ScrapeRequest) -> dict[str, Any]:
    collection = await get_collection()
    url = req.url.strip()
    pages = await scrape_website(url, max_pages=SCRAPE_MAX_PAGES)

    if not pages:
        raise HTTPException(status_code=400, detail="No content could be scraped from that URL.")

    auto_name = generate_auto_name(url, pages)
    pdf_filename = f"{auto_name}.pdf"
    pdf_bytes = pdf_bytes_from_pages(pages)
    pdf_asset = await store_pdf_asset(pdf_filename, pdf_bytes)

    full_text = "\n\n".join(page["content"] for page in pages)
    now = dt.datetime.utcnow()
    parsed = urlparse(url)
    title = extract_best_title(pages, url)

    document = {
        "url": url,
        "domain": parsed.netloc.replace("www.", ""),
        "title": title,
        "auto_name": auto_name,
        "pdf_filename": pdf_asset["pdf_filename"],
        "pdf_path": pdf_asset["pdf_path"],
        "pdf_storage": pdf_asset["pdf_storage"],
        "content": full_text,
        "content_preview": excerpt_text(full_text, 280),
        "pages": pages,
        "page_count": len(pages),
        "char_count": len(full_text),
        "created_at": now,
        "updated_at": now,
    }

    result = await collection.insert_one(document)
    stored = await collection.find_one({"_id": result.inserted_id})
    return {
        "message": "Scraped successfully.",
        "document": serialize_document(stored),
    }


@app.post("/api/chat")
async def chat_with_document(req: ChatRequest) -> dict[str, Any]:
    collection = await get_collection()
    row = await collection.find_one({"_id": parse_object_id(req.document_id)})
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = row.get("pages") or [{"url": row.get("url", ""), "content": row.get("content", "")}]
    selected_chunks = select_relevant_chunks(pages, req.message, limit=5)
    if not selected_chunks:
        raise HTTPException(status_code=400, detail="This document does not contain usable text for chat.")

    context_sections = []
    for index, chunk in enumerate(selected_chunks, start=1):
        context_sections.append(
            f"[Excerpt {index} | Source URL: {chunk['url']}]\n{chunk['content']}"
        )
    context_block = "\n\n".join(context_sections)

    fallback_message = f"I can't answer that from the selected PDF: {row['auto_name']}."
    system_prompt = f"""
You are a strict document-question answering assistant.

Selected PDF name: {row['auto_name']}
Selected PDF path: {row['pdf_path']}

Rules you must follow:
- Answer ONLY from the provided excerpts from the selected PDF.
- If the answer is not clearly present in the excerpts, reply exactly with: "{fallback_message}"
- If the user asks something unrelated to the selected PDF, reply exactly with: "{fallback_message}"
- Do not use outside knowledge.
- Do not guess, infer beyond the excerpts, or add extra facts.
- Keep the answer concise and directly tied to the selected PDF.

Selected document excerpts:
{context_block}
""".strip()

    try:
        groq_client = get_groq_client()
        chat_completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.message.strip()},
            ],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Groq request failed: {exc}") from exc

    answer = chat_completion.choices[0].message.content.strip()
    return {
        "response": answer,
        "document_name": row["auto_name"],
        "pdf_path": row["pdf_path"],
        "sources": [chunk["url"] for chunk in selected_chunks[:3]],
    }
