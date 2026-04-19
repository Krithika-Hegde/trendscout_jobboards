import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.append(str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright
import pandas as pd

from config import RAW_DIR, PROCESSED_DIR, HEADLESS

START_URL = "https://wellfound.com/remote"

def scrape_jobs():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print(f"Opening {START_URL}")
        page.goto(START_URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(8000)

        for _ in range(10):
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(1500)

        try:
            page.wait_for_selector('a[href*="/jobs/"]', timeout=30000)
        except Exception:
            print("Warning: job links did not appear before timeout.")

        title = page.title()
        html = page.content()

        print("PAGE TITLE:", title)
        print("HTML PREVIEW:")
        print(html[:1000])

        (RAW_DIR / "jobs_page.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(RAW_DIR / "jobs_page.png"), full_page=True)

        if "captcha-delivery" in html or "DataDome CAPTCHA" in html or "captcha" in title.lower():
            print("Warning: the page appears to be blocked by CAPTCHA/bot protection.")

        job_items = page.locator('a[href*="/jobs/"]').evaluate_all("""
        anchors => anchors.map(a => {
            const href = a.href || '';
            const text = (a.innerText || '').trim();
            let company = '';
            let location = '';
            const card = a.closest('article, li, div, section');
            if (card) {
                const texts = Array.from(card.querySelectorAll('span, div, p'))
                    .map(el => el.innerText.trim())
                    .filter(Boolean);
                const filtered = texts.filter(t => t !== text);
                if (filtered.length) {
                    company = filtered[0];
                    if (filtered.length > 1) {
                        location = filtered.slice(1, 3).join(' | ');
                    }
                }
            }
            return { text, href, company, location };
        })
        """)

        context.close()
        browser.close()

    rows = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for item in job_items:
        text = item.get("text", "")
        href = item.get("href", "")
        company = item.get("company") or None
        location = item.get("location") or None

        if not href or not text:
            continue

        if "wellfound.com" in href and "/jobs/" in href:
            rows.append({
                "title": text,
                "company": company,
                "location": location,
                "job_url": href,
                "scraped_at": scraped_at,
                "source": "wellfound"
            })

    df = pd.DataFrame(rows).drop_duplicates(subset=["job_url"])
    df.to_csv(PROCESSED_DIR / "jobs_list.csv", index=False)

    print(df.head(10))
    print(f"Saved {len(df)} jobs to data\\processed\\jobs_list.csv")

if __name__ == "__main__":
    scrape_jobs()