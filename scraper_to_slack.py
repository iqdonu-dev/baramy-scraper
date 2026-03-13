import os
import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TARGET_URL = "https://wp.nexon.com/community/server?boardId=3056&headlineId="

CHECK_MINUTES = 10

def send_to_slack(title, link):

    payload = {
        "text": f"새 글 발견\n{title}\n{link}"
    }

    requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=20)


def main():

    now = datetime.now()
    threshold = now - timedelta(minutes=CHECK_MINUTES)

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(TARGET_URL)
        page.wait_for_timeout(5000)

        rows = page.locator("tr")

        count = rows.count()

        print("row count:", count)

        for i in range(count):

            row = rows.nth(i)

            try:

                title_el = row.locator("a[href*='/community/server/']").first

                if title_el.count() == 0:
                    continue

                title = title_el.inner_text().strip()
                href = title_el.get_attribute("href")

                link = urljoin(TARGET_URL, href)

                date_text = row.inner_text()

                # 여기서 실제 날짜 parsing 필요
                # (예: "03.13 12:31" 같은 형태)

                print(title, link)

                send_to_slack(title, link)

            except:
                continue

        browser.close()


if __name__ == "__main__":
    main()
