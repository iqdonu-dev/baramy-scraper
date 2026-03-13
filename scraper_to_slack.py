# scraper_to_slack.py

import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta

# --- 설정 ---
# GitHub Secrets에서 Slack 웹훅 URL을 가져옴
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
# 스크레이핑할 DCinside 갤러리 주소
TARGET_URL = 'https://wp.nexon.com/community/server?boardId=3056&headlineId'
# 몇 분 이내의 새 글을 확인할지 설정 (GitHub Actions 실행 주기와 맞추는 것이 좋음)
CHECK_MINUTES = 10 

def send_to_slack(post):
    """게시물 정보를 Slack으로 전송하는 함수"""
    
    # Slack 메시지 형식 (Block Kit)
    slack_payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚽ 새 글 알림: {post['title']}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*작성자:*\n{post['writer']}"},
                    {"type": "mrkdwn", "text": f"*작성일:*\n{post['published_date'].strftime('%Y-%m-%d %H:%M')}"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "게시물 보러가기 🚀",
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
        response = requests.post(SLACK_WEBHOOK_URL, json=slack_payload)
        response.raise_for_status() # 요청 실패 시 오류 발생
        print(f"Slack 전송 성공: {post['title']}")
    except requests.exceptions.RequestException as e:
        print(f"Slack 전송 오류: {e}")

# --- 웹 스크레이핑 시작 ---
print(f"'{TARGET_URL}'에서 최근 {CHECK_MINUTES}분 내의 새 글을 확인합니다...")
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

try:
    response = requests.get(TARGET_URL, headers=headers)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"HTTP 요청 오류: {e}")
    exit()

soup = BeautifulSoup(response.text, 'html.parser')
now = datetime.now()
time_threshold = now - timedelta(minutes=CHECK_MINUTES)
new_post_count = 0

for post in soup.select('tr.ub-content.us-post:not(.notice)'):
    try:
        date_element = post.select_one('td.gall_date')
        if not date_element or not date_element.has_attr('title'):
            continue
            
        date_str = date_element['title']
        published_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

        # --- 핵심 로직: 최근 N분 이내에 작성된 글인지 확인 ---
        if published_date > time_threshold:
            title_element = post.select_one('td.gall_tit a')
            writer_element = post.select_one('td.gall_writer')

            post_data = {
                'title': title_element.get_text(strip=True),
                'link': 'https://gall.dcinside.com' + title_element['href'],
                'writer': writer_element.get('data-nick'),
                'published_date': published_date
            }
            
            # Slack으로 전송
            send_to_slack(post_data)
            new_post_count += 1

    except Exception as e:
        # print(f"개별 게시물 파싱 오류: {e}")
        continue

if new_post_count == 0:
    print(f"최근 {CHECK_MINUTES}분 내에 작성된 새로운 게시물이 없습니다.")
else:
    print(f"총 {new_post_count}개의 새로운 게시물을 Slack으로 전송했습니다.")
