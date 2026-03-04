# scraper_to_slack.py
import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

# --- 설정 ---
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TARGET_URL = "https://gall.dcinside.com/mgallery/board/lists?id=aion2"
CHECK_MINUTES = 10

# 상태 파일(마지막으로 보낸 글 번호 저장)
STATE_DIR = ".state"
STATE_FILE = os.path.join(STATE_DIR, "last_post_id.txt")

# KST 고정 (서버/러너 timezone에 흔들리지 않게)
try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except Exception:
    KST = None  # 최후 fallback (아래에서 처리)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def load_last_post_id() -> int | None:
    """마지막으로 전송한 post_id를 읽음. 없으면 None."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = f.read().strip()
            return int(s) if s else None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[WARN] state read failed: {e}")
        return None


def save_last_post_id(post_id: int) -> None:
    """마지막으로 전송한 post_id를 저장."""
    ensure_state_dir()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(str(post_id))
    except Exception as e:
        print(f"[WARN] state write failed: {e}")


def parse_post_id_from_href(href: str) -> int | None:
    """
    DCinside 글 링크에서 글 번호(no=) 추출
    예: /mgallery/board/view/?id=aion2&no=123456
    """
    try:
        qs = parse_qs(urlparse(href).query)
        if "no" in qs and qs["no"]:
            return int(qs["no"][0])
    except Exception:
        pass

    # 혹시 다른 형태면 숫자만 정규식으로 fallback
    m = re.search(r"(?:\bno=)(\d+)", href)
    if m:
        return int(m.group(1))
    return None


def parse_kst_datetime(date_str: str) -> datetime | None:
    """
    'YYYY-MM-DD HH:MM:SS' -> aware datetime(KST)
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        if KST is not None:
            return dt.replace(tzinfo=KST)
        return dt  # fallback: naive
    except Exception:
        return None


def now_kst() -> datetime:
    if KST is not None:
        return datetime.now(KST)
    return datetime.now()


def send_to_slack(post: dict) -> None:
    """게시물 정보를 Slack으로 전송 (Block Kit)"""
    slack_payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🆕 새 글 알림: {post['title']}", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*작성자:*\n{post['writer']}"},
                    {"type": "mrkdwn", "text": f"*작성일:*\n{post['published_at']}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "게시물 보러가기 🚀", "emoji": True},
                        "url": post["link"],
                    }
                ],
            },
            {"type": "divider"},
        ]
    }

    resp = requests.post(SLACK_WEBHOOK_URL, json=slack_payload, timeout=15)
    resp.raise_for_status()
    print(f"[OK] Slack sent: id={post['post_id']} title={post['title']}")


def main():
    if not SLACK_WEBHOOK_URL:
        print("[FATAL] SLACK_WEBHOOK_URL is not set. Check GitHub Secrets.")
        sys.exit(2)

    print(f"[INFO] Target: {TARGET_URL}")
    print(f"[INFO] Window: last {CHECK_MINUTES} minutes (KST fixed if available)")
    ensure_state_dir()

    last_sent_id = load_last_post_id()
    print(f"[INFO] last_sent_id = {last_sent_id}")

    # 요청
    try:
        r = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[FATAL] HTTP request failed: {e}")
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")

    # 시간 기준
    now = now_kst()
    threshold = now - timedelta(minutes=CHECK_MINUTES)
    print(f"[INFO] now = {now.isoformat()}")
    print(f"[INFO] threshold = {threshold.isoformat()}")

    posts = []
    for row in soup.select("tr.ub-content.us-post"):
        # 공지 제외
        if "notice" in row.get("class", []):
            continue

        date_el = row.select_one("td.gall_date")
        tit_el = row.select_one("td.gall_tit a")
        writer_el = row.select_one("td.gall_writer")

        if not date_el or not tit_el:
            continue

        # DCinside는 title 속성에 full datetime이 들어가는 경우가 많음
        date_str = date_el.get("title")
        if not date_str:
            continue

        published_dt = parse_kst_datetime(date_str)
        if published_dt is None:
            continue

        href = tit_el.get("href")
        if not href:
            continue

        link = urljoin("https://gall.dcinside.com", href)
        post_id = parse_post_id_from_href(href) or parse_post_id_from_href(link)

        # 작성자 fallback
        writer = ""
        if writer_el:
            writer = writer_el.get("data-nick") or writer_el.get_text(strip=True) or ""
        writer = writer if writer else "알 수 없음"

        title = tit_el.get_text(strip=True)

        posts.append(
            {
                "post_id": post_id,
                "title": title,
                "link": link,
                "writer": writer,
                "published_dt": published_dt,
            }
        )

    if not posts:
        print("[INFO] No posts parsed (selector might be broken or page blocked).")
        return

    # post_id 없는 것들은 뒤로
    posts_with_id = [p for p in posts if isinstance(p["post_id"], int)]
    if not posts_with_id:
        print("[WARN] Parsed posts but no post_id extracted. Will fall back to time-only check (may duplicate).")

    # 첫 실행: 스팸 방지 (상태파일 없으면 최신 글 id로 초기화만)
    newest_id = max((p["post_id"] for p in posts_with_id), default=None)
    if last_sent_id is None and newest_id is not None:
        save_last_post_id(newest_id)
        print(f"[INIT] State initialized. last_post_id set to {newest_id}. (No Slack messages sent)")
        return

    # 필터: (1) 최근 N분 이내 + (2) last_sent_id 보다 큰 글만
    candidates = []
    for p in posts_with_id:
        if p["published_dt"] <= threshold:
            continue
        if last_sent_id is not None and p["post_id"] <= last_sent_id:
            continue
        candidates.append(p)

    # 오래된 것부터 보내기
    candidates.sort(key=lambda x: x["post_id"])

    if not candidates:
        print("[INFO] No new posts to send.")
        return

    sent_max_id = last_sent_id or 0
    for p in candidates:
        published_at_str = p["published_dt"].strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "post_id": p["post_id"],
            "title": p["title"],
            "link": p["link"],
            "writer": p["writer"],
            "published_at": published_at_str,
        }

        try:
            send_to_slack(payload)
            sent_max_id = max(sent_max_id, p["post_id"])
        except Exception as e:
            print(f"[ERROR] Slack send failed for id={p['post_id']}: {e}")

    # 전송 성공한 것 기준으로 last_post_id 갱신
    if sent_max_id and sent_max_id != last_sent_id:
        save_last_post_id(sent_max_id)
        print(f"[INFO] Updated last_post_id -> {sent_max_id}")

    print(f"[DONE] Sent {len(candidates)} post(s).")


if __name__ == "__main__":
    main()
