import os
import requests
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TARGET_URL = "https://wp.nexon.com/community/server?boardId=3056&headlineId="

def send_to_slack(title, link, writer="알 수 없음", published_text="알 수 없음"):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        return

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"새 글 알림: {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*작성자:*\n{writer}"},
                    {"type": "mrkdwn", "text": f"*작성일:*\n{published_text}"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "게시물 보러가기",
                            "emoji": True
                        },
                        "url": link
                    }
                ]
            }
        ]
    }

    try:
        r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=20)
        r.raise_for_status()
        print(f"[SLACK] 전송 성공: {title}")
    except Exception as e:
        print(f"[SLACK] 전송 실패: {e}")

def main():
    print("[START] Playwright 크롤링 시작")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"[OPEN] {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

        # JS 렌더링 대기
        page.wait_for_timeout(5000)

        print("[INFO] 페이지 제목:", page.title())

        links = page.locator("a")
        count = links.count()
        print("[INFO] a 태그 수:", count)

        candidates = []

        for i in range(min(count, 120)):
            try:
                a = links.nth(i)
                text = a.inner_text().strip()
                href = a.get_attribute("href")

                if text or href:
                    full_link = urljoin(TARGET_URL, href or "")
                    print(f"[LINK {i}] text={text!r} href={href!r} full={full_link!r}")

                # 너무 짧은 메뉴 링크는 일단 제외
                if text and href and len(text) >= 2:
                    candidates.append((text, full_link))
            except Exception as e:
                print(f"[WARN] 링크 {i} 처리 실패: {e}")

        print("[INFO] 후보 링크 수:", len(candidates))

        # 디버깅용: 첫 번째 후보 1개만 슬랙 전송 테스트
        if candidates:
            title, link = candidates[0]
            print("[TEST] 첫 후보를 Slack으로 테스트 전송합니다.")
            send_to_slack(title=title, link=link)
        else:
            print("[INFO] 전송할 후보가 없습니다.")

        browser.close()
        print("[END] 완료")

if __name__ == "__main__":
    main()
