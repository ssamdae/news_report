from __future__ import annotations

import os
from pathlib import Path

import requests


TELEGRAM_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 15


def _telegram_config() -> tuple[str | None, str | None]:
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def _config_missing() -> bool:
    token, chat_id = _telegram_config()
    if token and chat_id:
        return False
    print("[TelegramNotifier] skip: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set")
    return True


def send_telegram_message(text: str) -> bool:
    if _config_missing():
        return False

    token, chat_id = _telegram_config()
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(
            url,
            data=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as error:
        print(f"[TelegramNotifier] message failed: {error}")
        return False

    print("[TelegramNotifier] message sent")
    return True


def send_telegram_document(file_path: str, caption: str | None = None) -> bool:
    if _config_missing():
        return False

    path = Path(file_path)
    if not path.exists():
        print(f"[TelegramNotifier] document skipped: file not found: {file_path}")
        return False

    token, chat_id = _telegram_config()
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendDocument"
    data = {
        "chat_id": chat_id,
        "caption": (caption or "")[:1000],
    }
    try:
        with path.open("rb") as file_obj:
            response = requests.post(
                url,
                data=data,
                files={"document": (path.name, file_obj, "application/pdf")},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
    except Exception as error:
        print(f"[TelegramNotifier] document failed: {error}")
        return False

    print("[TelegramNotifier] document sent")
    return True
