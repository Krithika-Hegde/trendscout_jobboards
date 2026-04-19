import sys
from pathlib import Path
from urllib.parse import urlparse
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pandas as pd

from config import PROCESSED_DIR, RAW_DIR, HEADLESS, REQUEST_DELAY_SECONDS, MAX_JOBS

sys.path.append(str(Path(__file__).resolve().parent))

def safe_filename(url):
    parsed = urlparse(url)
    base = parsed.netloc + parsed.path
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_")
    return safe[:180] or "job"


def normalize_text(text):
    if text is None:
        return None
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def extract_best_text(soup):
    candidates = soup.find_all(["article", "section", "main", "div"])
    best_text = ""
    for candidate in candidates:
        text = candidate.get_text(" ", strip=True)
        if len(text) > len(best_text):
            best_text = text
    if len(best_text) < 100:
        best_text = soup.body.get_text(" ", strip=True) if soup.body else best_text
    return normalize_text(best_text)


def extract_field_from_text(text, patterns):
    if not text:
        return None
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return normalize_text(m.group(1))
    return None


def extract_job_details(urls):
    detailed_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        for i, url in enumerate(urls, start=1):
            try:
                print(f"[{i}/{len(urls)}] Visiting {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(REQUEST_DELAY_SECONDS)

                html = page.content()
                soup = BeautifulSoup(html, "lxml")

                description = extract_best_text(soup)
                full_text = soup.get_text(" ", strip=True)

                salary = extract_field_from_text(
                    full_text,
                    [
                        r"(?:salary|compensation|pay range|base pay|annual pay|estimated pay)[\s:]*([^\n\r]{1,120})",
                        r"(\$[\d,.]+(?:\s*[-–to]+\s*\$[\d,.]+)?)"
                    ]
                )
                employment_type = extract_field_from_text(
                    full_text,
                    [
                        r"(?:employment type|job type|position type|role type)[\s:]*([^\n\r]{1,80})",
                    ]
                )

                raw_html_file = RAW_DIR / f"job_{i}_{safe_filename(url)}.html"
                raw_html_file.write_text(html, encoding="utf-8")

                detailed_rows.append({
                    "job_url": url,
                    "description": description,
                    "salary": salary,
                    "employment_type": employment_type,
                    "scrape_timestamp": pd.Timestamp.utcnow().isoformat() + "Z",
                    "raw_html_path": str(raw_html_file.name)
                })

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                detailed_rows.append({
                    "job_url": url,
                    "description": None,
                    "salary": None,
                    "employment_type": None,
                    "scrape_timestamp": pd.Timestamp.utcnow().isoformat() + "Z",
                    "raw_html_path": None
                })

        browser.close()

    df = pd.DataFrame(detailed_rows)
    df.to_csv(PROCESSED_DIR / "job_details.csv", index=False)
    print("Saved job details.")
    return df

if __name__ == "__main__":
    jobs_df = pd.read_csv(PROCESSED_DIR / "jobs_list.csv")
    urls = jobs_df["job_url"].dropna().unique().tolist()[:50]
    extract_job_details(urls)