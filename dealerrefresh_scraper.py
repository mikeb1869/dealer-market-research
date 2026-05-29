"""
DealerRefresh Forum Scraper (fixed URL patterns)
Install: pip install requests beautifulsoup4
Run: python dealerrefresh_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE_URL = "https://forum.dealerrefresh.com"

# (slug, label, max_pages) — each page ~20 threads
SUBFORUMS = [
    ("niada-sponsored-forum-for-independent-dealers.117", "NIADA Independent Dealer Forum", 3),
    ("crm-ilm-chat-desking-emails-phone-sms.5",           "CRM / ILM / DMS",                5),
]

REQUEST_DELAY = 1.5        # seconds between requests
MIN_REPLIES = 1            # skip threads with no replies
MAX_POSTS_PER_THREAD = 10  # set to None for all posts

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_soup(url):
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        elif resp.status_code == 403:
            print(f"  [403 login-gated] {url}")
        else:
            print(f"  [HTTP {resp.status_code}] {url}")
    except requests.RequestException as e:
        print(f"  [Error] {e}")
    return None


def clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    for bp in ["Click to expand...", "You must log in or register to reply here.", "Share:"]:
        text = text.replace(bp, "")
    return text.strip()


# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------

def scrape_thread_list(slug, max_pages):
    threads = []
    print(f"\n  Scanning thread list (up to {max_pages} pages)...")

    for page in range(1, max_pages + 1):
        if page == 1:
            url = f"{BASE_URL}/forums/{slug}/"
        else:
            url = f"{BASE_URL}/forums/{slug}/page-{page}"

        soup = get_soup(url)
        if not soup:
            break

        rows = (soup.select("div.structItem--thread")
                or soup.select("li.discussionListItem"))

        if not rows:
            print(f"    No rows on page {page} — stopping.")
            break

        added = 0
        for row in rows:
            title_el = (row.select_one(".structItem-title a:last-child")
                        or row.select_one("h3.title a"))
            if not title_el:
                continue

            title = clean(title_el.get_text())
            href = title_el.get("href", "")
            thread_url = BASE_URL + href if href.startswith("/") else href

            reply_el = row.select_one(".structItem-cell--meta dd")
            try:
                replies = int(re.sub(r"[^\d]", "", reply_el.get_text())) if reply_el else 0
            except (ValueError, AttributeError):
                replies = 0

            if replies < MIN_REPLIES:
                continue

            threads.append({"title": title, "url": thread_url, "reply_count": replies})
            added += 1

        print(f"    Page {page}: +{added} threads (total: {len(threads)})")
        if added == 0:
            break
        time.sleep(REQUEST_DELAY)

    return threads


def scrape_posts(thread):
    posts = []
    soup = get_soup(thread["url"])
    if not soup:
        return posts

    post_els = (soup.select("article.message--post")
                or soup.select("li.message"))

    for i, el in enumerate(post_els):
        if MAX_POSTS_PER_THREAD and i >= MAX_POSTS_PER_THREAD:
            break

        author_el = (el.select_one(".message-name .username")
                     or el.select_one(".username"))
        author = clean(author_el.get_text()) if author_el else "unknown"

        date_el = el.select_one("time")
        date_str = date_el.get("datetime", "") if date_el else ""

        body_el = (el.select_one(".message-body .bbWrapper")
                   or el.select_one(".messageText"))
        if not body_el:
            continue

        for quote in body_el.select("blockquote"):
            quote.decompose()

        content = clean(body_el.get_text(separator=" "))
        if len(content) < 40:
            continue

        posts.append({"post_number": i + 1, "author": author,
                      "date": date_str, "content": content})
    return posts


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    all_threads = []
    flat_posts = []

    for slug, label, max_pages in SUBFORUMS:
        print(f"\n{'='*60}\n{label}\n{'='*60}")
        threads = scrape_thread_list(slug, max_pages)

        print(f"\n  Fetching posts for {len(threads)} threads...")
        for i, thread in enumerate(threads):
            print(f"  [{i+1}/{len(threads)}] {thread['title'][:70]}")
            posts = scrape_posts(thread)
            thread.update({"subforum": label, "posts": posts, "posts_scraped": len(posts)})
            all_threads.append(thread)

            for post in posts:
                flat_posts.append({
                    "thread_title": thread["title"],
                    "thread_url": thread["url"],
                    "subforum": label,
                    "reply_count": thread["reply_count"],
                    **post,
                })
            time.sleep(REQUEST_DELAY)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"threads_{ts}.json", "w") as f:
        json.dump(all_threads, f, indent=2)
    with open(f"posts_{ts}.json", "w") as f:
        json.dump(flat_posts, f, indent=2)

    print(f"\nDone. {len(all_threads)} threads, {len(flat_posts)} posts.")
    print(f"Output: threads_{ts}.json  |  posts_{ts}.json")


if __name__ == "__main__":
    main()