"""보조 지표: 시작점 정확도 (서비스는 1위 구간의 시작점부터 재생하므로). 판정 기준은 바꾸지 않고 보조로만 보고한다.

- 시작 ±5초: 1위 구간 시작이 정답 시작(정답 구간이 여럿이면 가장 가까운 것) ±5초 안
- 앞 0~5초: 1위 시작이 정답 시작보다 0~5초 앞 (늦게 시작하면 내용을 놓치므로 「앞에서 시작」을 따로 봄)
- 시작 오차 중앙값(초, 절댓값)
- 무작위 기준: 영상마다 정답 평균 길이 구간을 무작위 위치에 놓았을 때의 기댓값 (질의별 1,000번, seed 0)

이미 저장된 dev 결과 파일(rows.json)만 읽는다. test는 다루지 않음.

    python ai/experiments/vlm_model/start_metrics.py --out docs/experiments/vlm_start_metrics_dev.md
"""
import argparse, json, random, statistics
from pathlib import Path

HERE = Path(__file__).parent
D = Path("/nfs/team/data/scenefinder_vlm")

# (표 이름, rows.json, rows 안 방식 키)
SOURCES = [
    ("B1 자막 검색 MiniLM", HERE / "results/prelim_dev/rows.json", "B1"),
    ("B2 구간 검색 CLIP 버전 (서비스 체크포인트·보정)", HERE / "results/prelim_dev/rows.json", "B2"),
    ("B3 main 서비스 결합", HERE / "results/prelim_dev/rows.json", "B3"),
    ("화면 검색 다국어 CLIP", HERE / "results/prelim_dev/rows.json", "F-CLIP"),
    ("화면 검색 Qwen3-VL-Emb 무학습", HERE / "results/prelim_dev/rows.json", "F-VLM"),
    ("(참고) 화면 검색 Qwen 1280", HERE / "results/prelim_dev/rows.json", "F-VLM-1280"),
    ("(참고) 자막 검색 Qwen", HERE / "results/prelim_dev/rows.json", "REF-SUB-VLM"),
    ("화면 검색 LoRA mix ep1", D / "lora_runs/mix/ep1/dev_eval/rows.json", "F-VLM"),
    ("화면 검색 LoRA mix ep2", D / "lora_runs/mix/ep2/dev_eval/rows.json", "F-VLM"),
    ("화면 검색 LoRA welfare ep1", D / "lora_runs/welfare/ep1/dev_eval/rows.json", "F-VLM"),
    ("화면 검색 LoRA welfare ep2", D / "lora_runs/welfare/ep2/dev_eval/rows.json", "F-VLM"),
    ("구간 검색 CLIP 재현 (모델만, 영상 전체)", D / "mr_runs/dev_eval/rows.json", "clip_repro"),
    ("구간 검색 VLM 토큰·한국어 (영상 전체)", D / "mr_runs/dev_eval/rows.json", "vlm_tok_ko"),
    ("구간 검색 VLM 토큰·영+한 (영상 전체)", D / "mr_runs/dev_eval/rows.json", "vlm_tok_enko"),
    ("구간 검색 VLM 토큰·영어 (영상 전체)", D / "mr_runs/dev_eval/rows.json", "vlm_tok_en"),
    ("구간 검색 VLM 1벡터·영+한 (영상 전체)", D / "mr_runs/dev_eval/rows.json", "vlm_pooled_enko"),
    ("구간 검색 CLIP 재현 (45칸 창)", D / "mr_runs/dev_eval_win/w45_s23/rows.json", "clip_repro"),
    ("구간 검색 VLM 토큰·한국어 (45칸 창)", D / "mr_runs/dev_eval_win/w45_s23/rows.json", "vlm_tok_ko"),
    ("구간 검색 VLM 추가 학습 (영상 전체)", D / "mr_runs/dev_eval_ft/w0_s0/rows.json", "vlm_tok_ko_ft"),
    ("구간 검색 VLM 추가 학습 (45칸 창)", D / "mr_runs/dev_eval_ft/w45_s23/rows.json", "vlm_tok_ko_ft"),
    ("N3 결합 (dev에서 고른 규칙)", HERE / "results/combo_dev/rows.json", "N3"),
]


def start_stats(rows, m):
    ok5 = early = 0; errs = []; n = 0
    for r in rows:
        if m not in r or not r[m].get("top5"):
            n += 1; errs.append(float("inf")); continue
        s = r[m]["top5"][0][0]; n += 1
        d = min((g[0] - s for g in r["gt"]), key=abs)   # >0 이면 정답보다 앞에서 시작
        errs.append(abs(d)); ok5 += abs(d) <= 5; early += 0 <= d <= 5
    return n, ok5, early, statistics.median(errs) if errs else None


def random_start(rows, durations, k=1000):
    rng = random.Random(0); ok5 = early = 0.0
    for r in rows:
        dur = durations[r["video"]]; L = statistics.mean(e - s for s, e in r["gt"])
        a = b = 0
        for _ in range(k):
            s = rng.uniform(0, max(0.0, dur - L)); d = min((g[0] - s for g in r["gt"]), key=abs)
            a += abs(d) <= 5; b += 0 <= d <= 5
        ok5 += a / k; early += b / k
    return ok5, early


def iou_r1(rows, m):
    return sum(r[m]["iou"] >= 0.3 for r in rows if m in r)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    labels = json.loads((HERE / "labels/review.json").read_text())
    durations = {k: v["duration"] for k, v in labels["videos"].items()}
    groups = [("전체", lambda r: True), ("S 말", lambda r: r["type"] == "S"), ("V 화면", lambda r: r["type"] == "V"),
              ("사용자 질문", lambda r: r["origin"] == "simulated_user")]
    L = ["# 보조 지표: 시작점 정확도 (dev, 판정 기준 아님)", "",
         "서비스는 1위 구간의 **시작점부터 재생**하므로 시작점을 따로 봅니다. 판정 기준(R@1 IoU≥0.3 등)은 그대로입니다.", "",
         "- **시작 ±5초**: 1위 시작이 정답 시작 ±5초 안 / **앞 0~5초**: 정답 시작보다 0~5초 앞에서 시작(늦게 시작하면 내용을 놓침) / "
         "**오차 중앙값**: |1위 시작 − 정답 시작|", "- 무작위: 정답 평균 길이 구간을 무작위 위치에 놓았을 때 기댓값", ""]
    base = json.loads((HERE / "results/prelim_dev/rows.json").read_text())
    for gname, gf in groups:
        L += [f"## {gname}", "", "| 방식 | 시작 ±5초 | 앞 0~5초 | 오차 중앙값(초) | (참고) R@1 IoU≥0.3 |", "|---|---|---|---|---|"]
        for name, path, m in SOURCES:
            if not path.exists():
                L.append(f"| {name} | (결과 없음) | | | |"); continue
            rows = [r for r in json.loads(path.read_text()) if gf(r)]
            if not rows or not any(m in r for r in rows):
                L.append(f"| {name} | (결과 없음) | | | |"); continue
            n, ok5, early, med = start_stats(rows, m)
            L.append(f"| {name} | {ok5 / n * 100:.0f}% ({ok5}/{n}) | {early / n * 100:.0f}% ({early}/{n}) | {med:.1f} | {iou_r1(rows, m)}/{n} |")
        rb = [r for r in base if gf(r)]
        o, e = random_start(rb, durations)
        L += [f"| 무작위 (기댓값) | {o / len(rb) * 100:.0f}% | {e / len(rb) * 100:.0f}% | – | – |", ""]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
