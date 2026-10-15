import html
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API = "https://www.googleapis.com/youtube/v3"


def _key() -> str:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY가 .env에 없습니다")
    return key


def _thumb(snippet: dict) -> str | None:
    th = snippet.get("thumbnails", {})
    return (th.get("medium") or th.get("default") or {}).get("url")


def search_youtube_page(
    query: str, max_results: int = 5, page_token: str | None = None
) -> tuple[list[dict], str | None]:
    """한 페이지를 검색합니다. (영상 목록, 다음 페이지 토큰)을 돌려줍니다.
    다음 페이지가 없으면 토큰은 None입니다. 호출 한 번에 유튜브 할당량 100이 듭니다."""
    params = {"part": "snippet", "q": query, "type": "video",
              "maxResults": max_results, "key": _key()}
    if page_token:
        params["pageToken"] = page_token
    r = requests.get(f"{API}/search", params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    items, seen = [], set()
    for it in data.get("items", []):
        vid = it.get("id", {}).get("videoId")
        if not vid or vid in seen:  # 같은 영상이 두 번 오면 한 번만
            continue
        seen.add(vid)
        items.append({
            "youtube_video_id": vid,
            "title": html.unescape(it["snippet"]["title"]),
            "channel_name": html.unescape(it["snippet"]["channelTitle"]),
            "thumbnail_url": _thumb(it["snippet"]),
            "published_at": it["snippet"]["publishedAt"],
        })
    durations = _fetch_durations([i["youtube_video_id"] for i in items])
    for i in items:
        i["duration"] = durations.get(i["youtube_video_id"])
    return items, data.get("nextPageToken")


def _fetch_durations(video_ids: list[str]) -> dict[str, int | None]:
    """검색 결과 카드에 보여줄 영상 길이(초). 실패해도 검색은 그대로 돌려줍니다.
    search API는 길이를 주지 않아 videos API를 한 번 더 부릅니다. (할당량 1)"""
    if not video_ids:
        return {}
    try:
        r = requests.get(
            f"{API}/videos",
            params={"part": "contentDetails", "id": ",".join(video_ids[:50]), "key": _key()},
            timeout=10,
        )
        r.raise_for_status()
    except requests.RequestException:
        return {}
    return {
        it["id"]: _parse_duration(it.get("contentDetails", {}).get("duration"))
        for it in r.json().get("items", [])
    }


def search_youtube(query: str, max_results: int = 5) -> list[dict]:
    return search_youtube_page(query, max_results)[0]


def _parse_duration(iso: str) -> int | None:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def fetch_video_meta(youtube_video_id: str) -> dict | None:
    """영상 1개의 제목/채널/길이를 조회합니다. 없는 영상이면 None."""
    r = requests.get(
        f"{API}/videos",
        params={"part": "snippet,contentDetails", "id": youtube_video_id, "key": _key()},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None
    sn = items[0]["snippet"]
    return {
        "title": html.unescape(sn["title"]),
        "channel_name": html.unescape(sn["channelTitle"]),
        "thumbnail_url": _thumb(sn),
        "published_at": sn["publishedAt"],
        "duration": _parse_duration(items[0]["contentDetails"].get("duration")),
    }


if __name__ == "__main__":
    items, nxt = search_youtube_page(sys.argv[1] if len(sys.argv) > 1 else "손흥민 골")
    for v in items:
        print(v["youtube_video_id"], "|", v["title"], "|", v["channel_name"])
    print("next_page_token:", nxt)