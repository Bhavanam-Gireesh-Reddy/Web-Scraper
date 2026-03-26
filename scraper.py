"""
Reusable scraping and PDF helpers for the Scrape Studio app.

Install:
  pip install crawl4ai python-dotenv xhtml2pdf

First-time crawl4ai setup (run once):
  crawl4ai-setup
"""

import asyncio
import html as html_module
import re
import urllib.parse
from collections import deque
from io import BytesIO
import os

import requests
from bs4 import BeautifulSoup

DEFAULT_MAX_PAGES = 20
DEFAULT_MAX_DEPTH = 2
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


UI_EXACT = {
    "Search...",
    "Ctrl K",
    "⌘K",
    "Navigation",
    "On this page",
    "Copy page",
    "Was this page helpful?",
    "YesNo",
    "Yes No",
    "⌘I",
    "Ctrl+I",
    "Security",
    "* Security",
    "Copy",
    "Get started",
    "About MCP",
    "Develop with MCP",
    "Developer tools",
    "Examples",
    "Version 2025-11-25 (latest)",
    "posts →",
}

SKIP_LINE_RE = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^#{1,6}\s*$",
        r"^#{5,6}\s+",
        r"^#{1,6}\s*(Get started|About MCP|Develop with MCP|Developer tools|Examples|Security|Utilities|Base Protocol|Client Features|Server Features|Specification)\s*$",
        r"^Copyright\s*©",
        r"^For web site terms",
        r"^\s*\[.*?\]\(.*?\)\s*$",
        r"^\s*https?://\S+\s*$",
        r"^\s*[-*]\s*\[.*?\]\(.*?\)\s*$",
        r"^\s*[,.\-–—|/\\:;!?()\[\]]*\s*$",
        r"^Go to Top",
        r"^posts\s*(fi|→)",
        r"Documentation\s*·\s*Posts\s*·\s*Archives",
        r"^\s*\(\s*$",
        r"^##\s+(Build servers|Build clients|Build MCP Apps|Understand concepts|Inspector Repository|Debugging Guide|Example servers|Example clients|Building a client)\s*$",
    ]
]


def clean_content(raw_text: str) -> str:
    lines = raw_text.split("\n")
    cleaned: list[str] = []
    prev_blank = False
    seen_short: set[str] = set()

    for line in lines:
        line = line.rstrip()
        stripped = line.strip()

        if stripped in UI_EXACT:
            continue

        if any(pattern.match(stripped) for pattern in SKIP_LINE_RE) and not stripped.startswith("!["):
            continue

        img_matches = re.findall(r"!\[.*?\]\(.*?\)", line)
        for index, img in enumerate(img_matches):
            line = line.replace(img, f"__IMG_TOKEN_{index}__")

        line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        line = re.sub(r"<https?://[^\s>]+>", "", line)
        line = re.sub(r"https?://\S+", "", line)
        line = re.sub(r"\(\s*\)", "", line)
        line = re.sub(r"\[\s*\]", "", line)
        line = re.sub(r"\(\s*$", "", line)

        for index, img in enumerate(img_matches):
            line = line.replace(f"__IMG_TOKEN_{index}__", img)

        line = line.rstrip()
        stripped = line.strip()

        if re.match(r"^\s*[,.\-–—|/\\:;!?()\[\]]*\s*$", stripped):
            continue

        if len(stripped) < 80 and not stripped.startswith("!["):
            if stripped in seen_short:
                continue
            seen_short.add(stripped)

        if not stripped:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    return "\n".join(cleaned)


def html_to_markdown_like_text(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "form", "button", "input", "aside"]):
        tag.decompose()

    lines: list[str] = []
    seen_lines: set[str] = set()

    def push(value: str) -> None:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            return
        if normalized in seen_lines:
            return
        seen_lines.add(normalized)
        lines.append(normalized)

    content_root = soup.find("main") or soup.find("article") or soup.body or soup

    for element in content_root.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code", "blockquote"]
    ):
        text = element.get_text(" ", strip=True)
        if not text:
            continue

        if element.name.startswith("h"):
            level = int(element.name[1])
            push(f"{'#' * min(level, 6)} {text}")
        elif element.name == "li":
            push(f"- {text}")
        elif element.name in {"pre", "code"}:
            push(f"```{text}```")
        else:
            push(text)

    for image in content_root.find_all("img"):
        src = image.get("src")
        if not src:
            continue
        alt = image.get("alt", "").strip()
        absolute_src = urllib.parse.urljoin(base_url, src)
        push(f"![{alt}]({absolute_src})")

    return clean_content("\n".join(lines))


def should_follow_link(candidate_url: str, root_netloc: str) -> bool:
    parsed = urllib.parse.urlparse(candidate_url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc != root_netloc:
        return False
    lowered = parsed.path.lower()
    blocked_suffixes = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".pdf",
        ".zip",
        ".rar",
        ".mp4",
        ".mp3",
        ".css",
        ".js",
        ".xml",
    )
    if lowered.endswith(blocked_suffixes):
        return False
    return True


def scrape_website_fallback(url: str, max_pages: int = DEFAULT_MAX_PAGES, max_depth: int = DEFAULT_MAX_DEPTH) -> list[dict[str, str]]:
    print("Primary browser crawler failed. Switching to static HTML fallback.")

    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    root = urllib.parse.urlparse(url)
    root_netloc = root.netloc
    queue: deque[tuple[str, int]] = deque([(url, 0)])
    visited: set[str] = set()
    pages: list[dict[str, str]] = []

    while queue and len(pages) < max_pages:
        current_url, depth = queue.popleft()
        normalized = current_url.rstrip("/")
        if normalized in visited or depth > max_depth:
            continue

        visited.add(normalized)
        try:
            response = session.get(current_url, timeout=20)
            response.raise_for_status()
        except Exception as exc:
            print(f"  Skipped {current_url[:100]} because of request error: {exc}")
            continue

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            continue

        cleaned = html_to_markdown_like_text(response.text, current_url)
        if cleaned.strip():
            pages.append({"url": response.url, "content": cleaned})
            print(f"  Saved page: {response.url[:100]}")

        if depth >= max_depth:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            next_url, _ = urllib.parse.urldefrag(urllib.parse.urljoin(response.url, anchor["href"]))
            if not should_follow_link(next_url, root_netloc):
                continue
            if next_url.rstrip("/") in visited:
                continue
            queue.append((next_url, depth + 1))

    print(f"\nPages scraped: {len(pages)}")
    print(f"Characters captured: {sum(len(page['content']) for page in pages):,}\n")
    return pages


async def scrape_website(url: str, max_pages: int = DEFAULT_MAX_PAGES, max_depth: int = DEFAULT_MAX_DEPTH) -> list[dict[str, str]]:
    print(f"\nScraping: {url}")
    print(f"  Crawling up to {max_pages} pages at depth {max_depth}.\n")

    # Vercel-friendly path: avoid heavyweight browser crawling in serverless deploys.
    if os.getenv("VERCEL"):
        print("Vercel environment detected. Using lightweight static HTML scraper.")
        return await asyncio.to_thread(scrape_website_fallback, url, max_pages, max_depth)

    try:
        from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

        try:
            from crawl4ai.deep_crawling import BFSDeepGraphCrawler
        except ImportError:
            from crawl4ai.deep_crawling import BFSDeepCrawlStrategy as BFSDeepGraphCrawler

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            deep_crawl_strategy=BFSDeepGraphCrawler(max_depth=max_depth, max_pages=max_pages),
        )

        seen_urls: set[str] = set()
        pages: list[dict[str, str]] = []

        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun(url, config=config)
            if not isinstance(results, list):
                results = [results]

            for result in results:
                if not result.success or not result.markdown:
                    continue

                normalized_url = result.url.rstrip("/")
                if normalized_url in seen_urls:
                    continue

                seen_urls.add(normalized_url)
                cleaned = clean_content(result.markdown)
                if cleaned.strip():
                    pages.append({"url": result.url, "content": cleaned})
                    print(f"  Saved page: {result.url[:100]}")

        print(f"\nPages scraped: {len(pages)}")
        print(f"Characters captured: {sum(len(page['content']) for page in pages):,}\n")
        return pages
    except NotImplementedError as exc:
        print(f"Browser crawler is unavailable on this Windows event loop: {exc}")
        return await asyncio.to_thread(scrape_website_fallback, url, max_pages, max_depth)
    except Exception as exc:
        message = str(exc).lower()
        if "playwright" in message or "subprocess" in message or "browser" in message:
            print(f"Browser crawler failed with a Playwright/browser error: {exc}")
            return await asyncio.to_thread(scrape_website_fallback, url, max_pages, max_depth)
        raise


def save_as_txt(pages: list[dict[str, str]], output_path: str = "clean_content.txt") -> None:
    print(f"Saving TXT: {output_path}")
    with open(output_path, "w", encoding="utf-8") as file_handle:
        for page in pages:
            file_handle.write("=" * 80 + "\n")
            file_handle.write(f"SOURCE: {page['url']}\n")
            file_handle.write("=" * 80 + "\n\n")
            file_handle.write(page["content"])
            file_handle.write("\n\n")
    print(f"TXT saved: {output_path}")


def md_to_html(text: str, base_url: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    code_buf: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def inline(value: str) -> str:
        images: list[str] = []

        def replace_image(match: re.Match[str]) -> str:
            alt_text = html_module.escape(match.group(1))
            img_url = urllib.parse.urljoin(base_url, match.group(2))
            images.append(f'<img src="{img_url}" alt="{alt_text}" />')
            return f"__IMG_PLACEHOLDER_{len(images) - 1}__"

        value = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, value)
        value = html_module.escape(value)
        value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
        value = re.sub(r"\*(.+?)\*", r"<i>\1</i>", value)
        value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)

        for index, img_tag in enumerate(images):
            value = value.replace(f"__IMG_PLACEHOLDER_{index}__", img_tag)

        return value

    for line in lines:
        if line.startswith("```"):
            if in_code:
                in_code = False
                code_text = html_module.escape("\n".join(code_buf))
                out.append(f"<pre>{code_text}</pre>")
                code_buf = []
            else:
                close_list()
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        if not line.strip():
            close_list()
            out.append("<br/>")
            continue

        if line.startswith("#### "):
            close_list()
            out.append(f"<h4>{inline(line[5:])}</h4>")
        elif line.startswith("### "):
            close_list()
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list()
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif line.startswith(("  - ", "  * ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li style='margin-left:20px'>{inline(line[4:])}</li>")
        elif len(line) > 2 and line[0].isdigit() and line[1] in ".)":
            close_list()
            out.append(f"<p style='margin-left:16px'>{inline(line)}</p>")
        elif line.startswith("    ") or line.startswith("\t"):
            close_list()
            out.append(f"<pre>{html_module.escape(line)}</pre>")
        elif line.startswith("|"):
            close_list()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= set("-: ") for cell in cells):
                continue
            row = "".join(f"<td>{inline(cell)}</td>" for cell in cells)
            out.append(f"<table><tr>{row}</tr></table>")
        elif set(line.strip()) <= set("-=*") and len(line.strip()) >= 3:
            close_list()
            out.append("<hr/>")
        else:
            close_list()
            out.append(f"<p>{inline(line)}</p>")

    close_list()
    return "\n".join(out)


def pages_to_html(pages: list[dict[str, str]]) -> str:
    css = """
    body {
        font-family: Helvetica, Arial, sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #111;
        margin: 0;
        padding: 0;
    }
    .page {
        padding: 20pt 30pt;
        page-break-after: always;
    }
    .url {
        font-size: 7pt;
        color: #999;
        border-bottom: 1pt solid #ddd;
        padding-bottom: 4pt;
        margin-bottom: 14pt;
        word-wrap: break-word;
    }
    h1 { font-size: 18pt; color: #173b67; margin: 14pt 0 6pt 0; }
    h2 { font-size: 14pt; color: #173b67; margin: 12pt 0 5pt 0; }
    h3 { font-size: 12pt; color: #2c5a2e; margin: 10pt 0 4pt 0; }
    h4 { font-size: 11pt; color: #555; margin: 8pt 0 3pt 0; }
    p  { margin: 4pt 0; }
    ul { margin: 4pt 0 4pt 16pt; padding: 0; }
    li { margin: 2pt 0; }
    pre {
        background: #f5f5f5;
        border-left: 3pt solid #173b67;
        padding: 6pt 10pt;
        font-size: 8pt;
        font-family: Courier, monospace;
        white-space: pre-wrap;
        word-wrap: break-word;
        margin: 6pt 0;
    }
    code {
        font-family: Courier, monospace;
        font-size: 9pt;
        background: #f0f0f0;
        padding: 1pt 3pt;
    }
    table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 10pt; }
    td { border: 1pt solid #ccc; padding: 4pt 8pt; }
    hr { border: none; border-top: 1pt solid #ddd; margin: 8pt 0; }
    b  { font-weight: bold; }
    i  { font-style: italic; }
    img {
        max-width: 100%;
        max-height: 400px;
        display: block;
        margin: 10pt 0;
    }
    """

    sections: list[str] = []
    for page in pages:
        content = md_to_html(page["content"], page["url"])
        sections.append(
            f"""
        <div class="page">
            <div class="url">{html_module.escape(page['url'])}</div>
            {content}
        </div>"""
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{css}</style>
</head>
<body>
{''.join(sections)}
</body>
</html>"""


def save_as_pdf(pages: list[dict[str, str]], output_path: str = "clean_content.pdf") -> None:
    print(f"Building PDF: {output_path}")
    pdf_bytes = pdf_bytes_from_pages(pages)

    with open(output_path, "wb") as file_handle:
        file_handle.write(pdf_bytes)

    print(f"PDF saved: {output_path}")


def pdf_bytes_from_pages(pages: list[dict[str, str]]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title("Scrape Studio Export")
    pdf.set_author("Scrape Studio")

    for page in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(0, 8, sanitize_pdf_text(page["url"]))
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        for raw_line in page["content"].splitlines():
            line = sanitize_pdf_text(raw_line)
            if not line:
                pdf.ln(4)
                continue
            pdf.multi_cell(0, 6, line)

    buffer = BytesIO()
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    elif isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1", errors="ignore")
    buffer.write(pdf_bytes)
    return buffer.getvalue()


def sanitize_pdf_text(value: str) -> str:
    # FPDF's built-in core fonts work best with latin-1 compatible text.
    return value.encode("latin-1", errors="replace").decode("latin-1")
