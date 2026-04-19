import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import PROCESSED_DIR

def extract_job_details(urls):
    rows = []

    for i, url in enumerate(urls, start=1):
        try:
            print(f"[{i}/{len(urls)}] Visiting {url}")
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            description_el = soup.select_one("div#content, div.content, section, main")
            description = description_el.get_text(" ", strip=True) if description_el else None

            rows.append({
                "job_url": url,
                "description": description
            })

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            rows.append({
                "job_url": url,
                "description": None
            })

    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED_DIR / "greenhouse_job_details.csv", index=False)
    print("Saved greenhouse job details.")
    return df

if __name__ == "__main__":
    jobs_df = pd.read_csv(PROCESSED_DIR / "greenhouse_jobs_list.csv")
    urls = jobs_df["job_url"].dropna().unique().tolist()[:50]
    extract_job_details(urls)