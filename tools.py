import json
import os
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ddgs import DDGS

LOCATION = "New Jersey, USA"

# ── Tool definitions (what Claude sees) ──────────────────────────────────────

tools = [
    {
        "name": "search_open_calls",
        "description": (
            "Search the web for art open calls, residencies, grants, and exhibition "
            "opportunities. Automatically scopes results to New Jersey and nearby areas. "
            "Returns a list of relevant opportunities with titles, URLs, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query, e.g. 'painting open call 2026' or "
                        "'artist residency deadline New Jersey'"
                    )
                },
                "category": {
                    "type": "string",
                    "enum": ["open_call", "residency", "grant", "exhibition", "all"],
                    "description": "Type of opportunity to search for"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_opportunity_details",
        "description": "Fetch the content of an art opportunity page given its URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the opportunity page"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "send_digest_email",
        "description": (
            "Send the daily art opportunities digest to the user via email. "
            "Call this after gathering and summarizing the opportunities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Full email body with the list of opportunities"
                }
            },
            "required": ["subject", "body"]
        }
    }
]


# ── Tool implementations ──────────────────────────────────────────────────────

def search_open_calls(query: str, category: str = "all") -> str:
    """Search DuckDuckGo for art opportunities near New Jersey."""
    # Build a location-aware query
    category_terms = {
        "open_call": "art open call submission",
        "residency": "artist residency",
        "grant": "artist grant funding",
        "exhibition": "art exhibition open call",
        "all": "art open call OR residency OR grant OR exhibition"
    }
    term = category_terms.get(category, "art open call")
    full_query = f"{query} {term} {LOCATION} 2026"

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(full_query, max_results=8):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_opportunity_details(url: str) -> str:
    """Fetch raw text content from an opportunity URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ArtScopingBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Strip tags crudely — good enough for Claude to parse the text
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        # Limit to first 3000 chars to keep tokens manageable
        return json.dumps({"url": url, "content": text[:3000]})
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)})


def send_digest_email(subject: str, body: str) -> str:
    """Send digest via Gmail SMTP."""
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("DIGEST_RECIPIENT_EMAIL", sender)

    if not sender or not password:
        return json.dumps({
            "status": "error",
            "message": "GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env"
        })

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        return json.dumps({"status": "sent", "to": recipient})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Router ────────────────────────────────────────────────────────────────────

def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "search_open_calls":
        return search_open_calls(**tool_input)
    elif tool_name == "get_opportunity_details":
        return get_opportunity_details(**tool_input)
    elif tool_name == "send_digest_email":
        return send_digest_email(**tool_input)
    else:
        return f"Unknown tool: {tool_name}"
