"""실제 서비스 검색 경로(POST /api/search)로 검수 질의를 보내 결과를 저장합니다.

설명문 검색 「끔」·「켬」 백엔드에 같은 질의를 보내 비교하기 위한 것입니다 (docs/design/vlm_search.md 「검증 계획」).
결합 방식(CAPTION_FUSION)·구간 확장(CAPTION_SPAN_EXPAND_SEC)은 백엔드 .env/환경변수로 정하므로, 후보마다 백엔드를
그 값으로 띄운 뒤 --label을 바꿔 실행합니다.

    python ai/experiments/vlm_service_compare/run.py --base http://127.0.0.1:8001 --label on_zmax2 \
        --queries ~/scenefinder_eval/labels_draft.json --subset dev --out ~/scenefinder_eval/vlm_service

- human_reviewed·human 질의만 씀 (ai_draft는 뺌)
- 질의마다 1번 보내고, 응답 시간은 같은 질의를 --repeat번 더 보내 중앙값을 씀 (첫 요청은 캐시가 비어 있을 수 있어 따로 기록)
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "translation_compare"))
import query_set  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--subset", choices=query_set.SUBSETS, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--repeat", type=int, default=2)
    a = ap.parse_args()

    qs = query_set.load(Path(a.queries).expanduser(), subset=a.subset)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for num, key, typ, query, gts in qs.queries:
        info = qs.info[num]
        if info.get("source") == "ai_draft":
            continue
        yid = qs.videos[key]["youtube_id"]
        body = {"youtube_video_id": yid, "query": query, "top_k": a.top_k}
        t0 = time.perf_counter()
        r = requests.post(f"{a.base}/api/search", json=body, timeout=120)
        first_ms = (time.perf_counter() - t0) * 1000
        d = r.json()
        if r.status_code != 200 or d.get("status") != "INDEXED":
            raise SystemExit(f"#{num} {yid}: HTTP {r.status_code} {d.get('status')} {d.get('error') or d.get('message')}")
        times = []
        for _ in range(a.repeat):
            t0 = time.perf_counter()
            requests.post(f"{a.base}/api/search", json=body, timeout=120).raise_for_status()
            times.append((time.perf_counter() - t0) * 1000)
        rows.append({
            "num": num, "video": key, "youtube_id": yid, "type": typ, "query": query,
            "gt": [list(g) for g in gts], **info,
            "caption_status": d.get("caption_status"),
            "moments": [{"start": m["start_time"], "end": m["end_time"], "score": m.get("score"),
                         "source": m.get("source")} for m in d.get("results", [])],
            "first_ms": round(first_ms, 1),
            "ms": round(statistics.median(times), 1) if times else round(first_ms, 1),
        })
        print(f"#{num} {typ} {len(rows[-1]['moments'])}개 {rows[-1]['ms']:.0f}ms", flush=True)
    path = out / f"{a.label}.json"
    path.write_text(json.dumps({"meta": {"label": a.label, "base": a.base, "subset": a.subset,
                                         "queries": str(a.queries), "top_k": a.top_k,
                                         "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                                "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)}개 저장: {path}")


if __name__ == "__main__":
    main()
