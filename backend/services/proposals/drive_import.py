"""Live Google Drive import for the proposal module.

Uses the service-account JSON stored in Settings → Integrations → Google Drive to
read Google Docs (exported as plain text) so a PM can turn a finalised brief in
Drive into a proposal — the same AI→brief flow as the manual upload path.

The service account must have the target Doc shared with its client_email
(or the configured default folder shared with it). Scope: drive.readonly.
"""
import io
import json
import logging
import re
from typing import List, Optional, Tuple

from database import integration_settings_collection

logger = logging.getLogger(__name__)

ORG_ID = "default"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


async def _get_drive_config() -> Optional[dict]:
    """Return the stored Google Drive config {service_account_json, default_folder_id}
    if enabled and credentials present, else None."""
    try:
        doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    except Exception as e:
        logger.warning(f"[drive] settings lookup failed: {e}")
        return None
    gd = (doc or {}).get("google_drive") or {}
    if not gd.get("enabled"):
        return None
    sa = gd.get("service_account_json")
    if not sa:
        return None
    return {"service_account_json": sa, "default_folder_id": gd.get("default_folder_id") or ""}


def _build_drive_service(service_account_json: str):
    """Build an authenticated Drive v3 client from the SA JSON string. Raises
    ValueError with a friendly message on bad credentials."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except json.JSONDecodeError:
        raise ValueError("The saved Google service-account JSON is not valid JSON.")
    except Exception as e:
        raise ValueError(f"Could not initialise Google Drive client: {e}")


_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
_FILE_ID_RE = re.compile(r"[-\w]{25,}")


def extract_doc_id(url_or_id: str) -> Optional[str]:
    """Accept a full Google Doc URL or a raw file id and return the file id."""
    if not url_or_id:
        return None
    s = url_or_id.strip()
    m = _DOC_ID_RE.search(s)
    if m:
        return m.group(1)
    if "/" not in s and _FILE_ID_RE.fullmatch(s):
        return s
    m2 = _FILE_ID_RE.search(s)
    return m2.group(0) if m2 else None


async def list_drive_docs(folder_id: Optional[str] = None, limit: int = 50) -> Tuple[List[dict], Optional[str]]:
    """List Google Docs the service account can see (optionally within a folder).
    Returns (files, error_message). files = [{id, name, modified}]."""
    cfg = await _get_drive_config()
    if not cfg:
        return [], "Google Drive is not configured or is disabled in Settings."
    try:
        service = _build_drive_service(cfg["service_account_json"])
    except ValueError as e:
        return [], str(e)

    folder = folder_id or cfg.get("default_folder_id") or ""
    q = "mimeType='application/vnd.google-apps.document' and trashed=false"
    if folder:
        q += f" and '{folder}' in parents"
    try:
        import asyncio

        def _list():
            return service.files().list(
                q=q, pageSize=min(limit, 100),
                fields="files(id,name,modifiedTime)",
                orderBy="modifiedTime desc",
            ).execute()
        resp = await asyncio.to_thread(_list)
        files = [
            {"id": f["id"], "name": f.get("name", "Untitled"), "modified": f.get("modifiedTime")}
            for f in resp.get("files", [])
        ]
        if not files:
            return [], ("No Google Docs visible to the service account. Share the Doc "
                        "(or a folder) with the service account's client_email, or set a default folder.")
        return files, None
    except Exception as e:
        logger.error(f"[drive] list failed: {e}")
        return [], f"Could not list Google Docs: {e}"


async def fetch_doc_text(doc_id_or_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch a Google Doc exported as plain text. Returns (text, error_message)."""
    cfg = await _get_drive_config()
    if not cfg:
        return None, "Google Drive is not configured or is disabled in Settings."
    doc_id = extract_doc_id(doc_id_or_url)
    if not doc_id:
        return None, "Couldn't determine the Google Doc id from that link."
    try:
        service = _build_drive_service(cfg["service_account_json"])
    except ValueError as e:
        return None, str(e)
    try:
        import asyncio

        def _export():
            from googleapiclient.http import MediaIoBaseDownload
            request = service.files().export_media(fileId=doc_id, mimeType="text/plain")
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
            return buf.getvalue().decode("utf-8", errors="ignore")
        text = await asyncio.to_thread(_export)
        text = (text or "").strip()
        if not text:
            return None, "The Google Doc appears to be empty."
        MAX = 24000
        if len(text) > MAX:
            text = text[:MAX] + "\n\n[...truncated...]"
        return text, None
    except Exception as e:
        logger.error(f"[drive] export failed: {e}")
        msg = str(e)
        if "404" in msg or "notFound" in msg:
            return None, ("Doc not found or not shared with the service account. Share it with the "
                          "service account's client_email (Viewer is enough).")
        if "403" in msg:
            return None, ("Access denied. Share the Doc with the service account's client_email, "
                          "and ensure the Drive API is enabled for that Google Cloud project.")
        return None, f"Could not read the Google Doc: {e}"
