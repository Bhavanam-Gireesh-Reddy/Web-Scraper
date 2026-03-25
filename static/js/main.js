function setStatusBox(message, variant) {
    const statusBox = document.getElementById("scrape-status");
    if (!statusBox) return;

    statusBox.className = `status-box visible ${variant}`;
    statusBox.innerHTML = message;
}

function appendChatMessage(text, kind) {
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return;

    const bubble = document.createElement("div");
    bubble.className = kind === "user" ? "user-message" : "assistant-message";
    bubble.innerHTML = text.replace(/\n/g, "<br>");
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function handleScrapeSubmit(event) {
    event.preventDefault();

    const input = document.getElementById("url-input");
    const button = document.getElementById("scrape-submit");
    if (!input || !button) return;

    const url = input.value.trim();
    if (!url) {
        setStatusBox("Enter a valid URL before starting the scrape.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Scraping in progress...";
    setStatusBox("Scraping the website, generating a PDF name, saving to MongoDB, and preparing the selected chat workspace.", "");

    try {
        const response = await fetch("/api/scrape", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "The scrape request failed.");
        }

        const documentInfo = data.document;
        setStatusBox(
            `Saved as <strong>${documentInfo.auto_name}</strong>. Opening the exact document workspace used by the chatbot...`,
            "success"
        );

        window.setTimeout(() => {
            window.location.href = `/documents/${documentInfo.id}`;
        }, 900);
    } catch (error) {
        setStatusBox(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Scrape, Save, and Open Chat";
    }
}

async function handleChatSubmit(event) {
    event.preventDefault();

    const workspace = document.getElementById("document-workspace");
    const input = document.getElementById("chat-input");
    const button = document.getElementById("chat-submit");
    if (!workspace || !input || !button) return;

    const message = input.value.trim();
    const documentId = workspace.dataset.documentId;
    if (!message) return;

    appendChatMessage(`<strong>You:</strong> ${message}`, "user");
    input.value = "";
    button.disabled = true;
    button.textContent = "Thinking...";

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                document_id: documentId,
                message
            })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "The chatbot request failed.");
        }

        let assistantText = `<strong>PDF in use:</strong> ${data.document_name}<br>${data.response}`;
        if (data.sources && data.sources.length) {
            assistantText += `<br><br><strong>Sources:</strong><br>${data.sources.map((item) => item).join("<br>")}`;
        }
        appendChatMessage(assistantText, "assistant");
    } catch (error) {
        appendChatMessage(`<strong>Error:</strong> ${error.message}`, "assistant");
    } finally {
        button.disabled = false;
        button.textContent = "Ask Chatbot";
    }
}

function initHistorySearch() {
    const searchInput = document.getElementById("history-search");
    const cards = Array.from(document.querySelectorAll(".history-card"));
    if (!searchInput || !cards.length) return;

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim().toLowerCase();
        cards.forEach((card) => {
            const haystack = card.dataset.search || "";
            card.style.display = haystack.includes(query) ? "" : "none";
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const scrapeForm = document.getElementById("scrape-form");
    if (scrapeForm) {
        scrapeForm.addEventListener("submit", handleScrapeSubmit);
    }

    const chatForm = document.getElementById("chat-form");
    if (chatForm) {
        chatForm.addEventListener("submit", handleChatSubmit);
    }

    initHistorySearch();
});
