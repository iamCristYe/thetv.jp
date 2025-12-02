#!/usr/bin/env python3
"""Fetch all item images from the Nogizaka46 shop category page and send them to a Telegram chat.

Usage:
    Set environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID then run:
        python send_first_img.py

Notes:
    - `TELEGRAM_CHAT_ID` can be a group chat id (negative number) or channel id.
    - The script finds all `<div id="item_...">` blocks on the page, extracts each `<img>` src and the `<dd>` caption,
        downloads each image, and sends them one-by-one to Telegram.
    - Optional env var `TELEGRAM_DELAY_SECONDS` (default 1) controls delay between sends to avoid rate limits.
"""
import os
import re
import sys
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

URL = "https://thetv.jp/news/detail/1310405/"


def get_all_items(url: str, i: str) -> List[Tuple[str, str]]:
    """Return list of (image_url, caption) for all item divs on the page.

    Returns an empty list if none found.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; send_first_img/1.0)"}
    resp = requests.get(f"{url}", timeout=15, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for li in soup.find_all("div", class_="newsimage")[0].find_all("li"):
        print(li)
        a = li.find("a")
        if not a or not a.get("href"):
            continue
        src = (
            "https://thetv.jp/"
            + a["href"].strip()[:-1].replace("/news/detail/", "/i/nw/")
            + ".jpg"
        )
        print(src)
        # Normalize protocol-relative URLs
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = requests.compat.urljoin(url, src)

        img = li.find("img")
        caption = img["alt"] if img else ""
        items.append((src, caption))
        print(items)

    return items


def download_image_bytes(
    session: requests.Session, image_url: str
) -> Tuple[bytes, str]:
    """Download the image and return (bytes, filename).

    The filename is derived from the URL path or falls back to 'file'.
    """
    resp = session.get(image_url, timeout=20)
    resp.raise_for_status()
    content = resp.content
    # try to derive filename from URL
    try:
        from urllib.parse import urlparse, unquote

        path = urlparse(image_url).path
        name = unquote(path.split("/")[-1]) or "file"
    except Exception:
        name = "file"

    # Ensure filename has an image extension for Telegram; append .jpg when missing
    lower = name.lower()
    if not lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        name = name + ".jpg"

    return content, name


def send_photo_telegram(
    session: requests.Session,
    bot_token: str,
    chat_id: str,
    file_bytes: bytes,
    filename: str,
    caption: str,
):
    """Send a file as photo via Telegram sendPhoto API."""
    api = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    files = {"photo": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    resp = session.post(api, data=data, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or 1
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or 2
    if not token or not chat_id:
        print(
            "Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables."
        )
        sys.exit(2)

    for i in range(1, 2):
        try:
            items = get_all_items(URL, i)
        except Exception as e:
            print("Error fetching/parsing page:", e)
            sys.exit(1)

        if not items:
            print("No items found on the page.")
            continue

        delay = float(os.getenv("TELEGRAM_DELAY_SECONDS", "1"))

        session = requests.Session()
        sent = 0
        for idx, (image_url, caption) in enumerate(items, start=1):
            print(f"[{idx}/{len(items)}] Processing: {image_url}")
            try:
                file_bytes, filename = download_image_bytes(session, image_url)
            except Exception as e:
                print(f"  Error downloading image: {e}")
                continue

            try:
                res = send_photo_telegram(
                    session, token, chat_id, file_bytes, filename, caption
                )
                ok = res.get("ok")
                print(f"  Sent as photo '{filename}', ok={ok}")
                sent += 1
                # extra pause after sending to be polite to Telegram
                try:
                    import time

                    time.sleep(3)
                except Exception:
                    pass
            except Exception as e:
                print(f"  Error sending to Telegram: {e}")
                # continue to next image

            # polite delay to avoid hitting rate limits
            try:
                import time

                time.sleep(delay)
            except Exception:
                pass

        print(f"Done. Sent {sent}/{len(items)} images.")


if __name__ == "__main__":
    main()
