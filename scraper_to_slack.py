import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
from urllib.parse import urljoin

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
TARGET_URL = 'https://wp.nexon.com/community/server?boardId=3056&headlineId'
CHECK_MINUTES = 10

def send_to_slack(post):
    slack_payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"새 글 알림: {post['title']}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*작성자:*\n{post.get('writer', '알 수 없음')}"},
                    {"type": "mrkdwn", "text": f"*작성일:*\n{post.get('published_text', '알 수 없음')}"}
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
                        "url": post['link']
                    }
                ]
            },
            {"type": "divider"}
        ]
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=slack_payload, timeout=20)
        response.raise_for_status()
        print(f"Slack 전송 성공: {post['title']}")
    except requests.exceptions.RequestException as e:
        print(f"Slack 전송 오류: {e}")
        if hasattr(e, "response") and e.response is not None:
            print("Slack 응답:", e.response.text)

print(f"'{TARGET_URL}'에서 최근 {CHECK_MINUTES}분 내 새 글을 확인합니다...")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
}

try:
    response = requests.get(TARGET_URL, headers=headers, timeout=20)
    print("HTTP status:", response.status_code)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"HTTP 요청 오류: {e}")
    raise SystemExit(1)

print("응답 일부 확인:")
print(response.text[:3000])

soup = BeautifulSoup(response.text, 'html.parser')

# 디버깅: 페이지 제목
print("페이지 제목:", soup.title.string if soup.title else "제목 없음")

# 일단 링크를 가진 요소를 일부 확인
links = soup.select("a")
print(f"a 태그 수: {len(links)}")
for a in links[:20]:
    print("LINK:", a.get_text(strip=True), a.get("href"))

# 실제 사이트 구조를 확인한 뒤 아래 부분을 넥슨 사이트용으로 교체해야 함
posts = soup.select("article, li, tr, div")
print(f"후보 요소 수: {len(posts)}")

if not posts:
    print("게시글 후보를 찾지 못했습니다. 이 페이지는 JS 렌더링일 가능성이 높습니다.")
