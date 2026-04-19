import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import PROCESSED_DIR, RAW_DIR

START_URL = "https://job-boards.greenhouse.io/xai"

def scrape_greenhouse_jobs():
    print(f"Opening {START_URL}")
    response = requests.get(
        START_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
        allow_redirects=True
    )

    print("Final URL:", response.url)
    print("Status code:", response.status_code)
    response.raise_for_status()

    html = response.text
    (RAW_DIR / "greenhouse_page.html").write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    jobs = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        title = a.get_text(" ", strip=True)

        if not href or not title:
            continue

        if href.startswith("/"):
            href = "https://job-boards.greenhouse.io" + href

        if "/jobs/" in href:
            jobs.append({
                "company": "xAI",
                "department": None,
                "title": title,
                "location": None,
                "job_url": href
            })

    df = pd.DataFrame(jobs).drop_duplicates(subset=["job_url"])
    df.to_csv(PROCESSED_DIR / "greenhouse_jobs_list.csv", index=False)

    print(df.head(10))
    print(f"Saved {len(df)} jobs to data\\processed\\greenhouse_jobs_list.csv")
    return df

if __name__ == "__main__":
    scrape_greenhouse_jobs()