"""설명문 묶음 크기(1/4/8)별 비교 문서를 만듭니다 (dev 영상만).

    python ai/experiments/translation_compare/caption_batch_compare.py \
        --runs 1=~/scenefinder_eval/results_v2 4=~/scenefinder_eval/results_v2_b4_dev 8=~/scenefinder_eval/results_v2_b8 \
        [--output docs/experiments/caption_batch_compare.md]

- 각 결과 폴더는 같은 라벨·같은 feature·같은 자막에 설명문만 묶음 크기를 바꿔 만든 것입니다(captions.py --batch-size).
- 설명문 일치율·글자 유사도는 첫 번째(묶음 1) 설명문과 비교합니다.
- 지표는 dev 영상의 질의만으로 계산합니다(eval_youtube_videos.tsv의 split).
"""
import argparse
import difflib
import json
from pathlib import Path

import query_set
import summary

ROOT = Path(__file__).resolve().parents[3]
METHODS = [("e_qwen_incl", "(e) 설명문 검색"), ("e_M1", "(e) + 앞뒤 2초 확장 (M1, 탐색적)"),
           ("A", "융합 A"), ("B_M0", "융합 B")]
CAUSE = """\
## 원인

같은 프레임인데 묶음 크기에 따라 설명문이 달라지는 원인을 확인했습니다(eggroll_paik 8장으로 실험).

| 확인 | 결과 |
|---|---|
| 생성 방식 | 모델 기본 설정은 `do_sample=True`(temperature 0.7)지만 captions.py가 `do_sample=False`를 넘겨 **greedy**. 같은 묶음 크기로 두 번 돌리면 8/8 같음 |
| 패딩 | 왼쪽 패딩으로 설정돼 있으나, 같은 영상의 프레임은 크기(640×360)와 프롬프트가 같아 **패딩이 생기지 않음** (8장 모두 296토큰) |
| 다른 이미지의 영향 | 같은 그림 8장을 묶어도 vision 임베딩이 혼자일 때와 다름 → 다른 이미지가 섞여 생기는 문제가 아님 |
| 정밀도 | 혼자 vs 8장 묶음의 vision 임베딩 상대 차이: **bfloat16 평균 4.9%(최대 7.1%), float32 0.001%** |

**결론:** 버그가 아니라 bfloat16 계산 오차입니다. 묶음 크기에 따라 GPU 연산 방식이 달라지고, bf16에서는 그 차이가 vision 임베딩에서 약 5%까지 \
벌어집니다. greedy 생성은 앞 단어 하나만 달라져도 뒤 문장이 갈라지므로 설명문이 달라집니다. 1장씩 처리한 결과도 같은 크기의 bf16 오차를 가진 \
하나의 결과일 뿐 '정답'은 아닙니다. 고칠 설정(패딩·샘플링)은 없었고, 차이를 없애려면 vision 부분을 float32로 돌려야 합니다(속도·메모리 비용, 이번에는 적용 안 함).
"""

INTERPRETATION = """\
1. **묶음 4와 8은 묶음 1과 같은 정도로 다릅니다(같은 설명문 37%·38%, 글자 유사도 0.85).** 묶음을 줄인다고 1장씩 처리에 가까워지지 않습니다. \
bf16 오차는 묶음 크기가 1이 아니면 비슷하게 생깁니다.
2. **검색 결과에 묶음 크기에 따른 일정한 방향이 없습니다.** 묶음 4가 1과 8 사이에 오지 않고, 지표에 따라 8보다 낮기도 합니다. \
차이는 dev 47개 중 1~4개로, 설명문을 다시 만들 때 생기는 흔들림(잡음) 수준으로 봅니다. 묶음 1이 조금씩 높지만 \
이 데이터로는 '1장씩이 더 낫다'고 말할 수 없습니다.
3. **권장: 묶음 8 유지.** 1장씩보다 약 6배 빠르고(장당 2.29초 → 0.38초) GPU 메모리 차이는 0.5GiB입니다. 묶음 4는 8보다 느리고 \
결과가 나은 것도 아닙니다.
4. **앞으로 비교할 때의 기준:** 설명문을 다시 만드는 것만으로 (e) IoU ≥ 0.3이 dev 47개 중 최대 3개, R@3이 최대 3개 움직입니다. \
설명문을 새로 만드는 설정 비교(프롬프트·모델 등)에서는 이보다 큰 차이만 의미 있게 봐야 합니다. 같은 설명문 파일을 쓰는 비교(임베딩 모델, \
구간 규칙 등)는 이 잡음이 없습니다.
5. 설명문을 묶음 크기와 상관없이 똑같이 만들려면 vision 부분을 float32로 돌려야 합니다(혼자 vs 묶음 차이 0.001%). \
속도·메모리 비용이 있어 이번에는 적용하지 않았습니다.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True, help="묶음크기=결과폴더 (첫 번째가 비교 기준)")
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/caption_batch_compare.md"))
    args = parser.parse_args()
    runs = [(int(x.split("=", 1)[0]), Path(x.split("=", 1)[1]).expanduser()) for x in args.runs]
    qs = query_set.load(runs[0][1] / "labels_snapshot.json", "dev")
    nums = {q[0] for q in qs.queries}
    keys = qs.video_keys

    data = []
    for bs, out in runs:
        cap = json.loads((out / "captions_qwen_incl.json").read_text(encoding="utf-8"))
        res = json.loads((out / "results.json").read_text(encoding="utf-8"))
        fus = {r["num"]: r for r in json.loads((out / "fusion_results.json").read_text(encoding="utf-8"))["rows"]}
        rows = []
        for r in res["rows"]:
            if r["num"] not in nums:
                continue
            r = summary.annotate(dict(r), qs)
            for k in ("e_M1", "A", "B_M0"):
                r[k] = fus[r["num"]][k]
            rows.append(r)
        meta = cap["meta"]
        timing = meta["single"] if meta.get("result_batch_size", 1) == 1 else meta["batch"]
        frames = sum(timing[k]["frames"] for k in keys)
        secs = sum(timing[k]["total_sec"] for k in keys)
        peak = meta.get("peak_gpu_gib_single") if meta.get("result_batch_size", 1) == 1 else meta["batch"].get("peak_gpu_gib")
        data.append({"bs": bs, "caps": cap["videos"], "rows": rows, "frames": frames, "secs": secs, "peak": peak})

    base = data[0]
    L = ["# 설명문 묶음 크기 비교 (1 / 4 / 8장, dev)", "",
         "Qwen3-VL-4B 설명문을 묶음 크기만 바꿔 만들고 dev 영상 "
         f"{len(keys)}개({', '.join(keys)})의 질의 {len(base['rows'])}개로 비교했습니다. "
         "자막·CLIP feature·라벨은 모두 같습니다. 묶음 1은 [eval_v2.md](eval_v2.md)의 처음 결과, 묶음 8은 지금 기본값입니다.", "",
         CAUSE, "## 결과 (dev)", "",
         "| 묶음 | 장당 생성 시간 | GPU 최대 할당 | 묶음 1과 같은 설명문 | 평균 글자 유사도 |", "|---|---|---|---|---|"]
    for d in data:
        same = total = 0
        sims = []
        for k in keys:
            for x, y in zip(base["caps"][k], d["caps"][k]):
                total += 1
                same += x["text"] == y["text"]
                sims.append(difflib.SequenceMatcher(None, x["text"], y["text"]).ratio())
        peak = f"{d['peak']:.1f} GiB" if d["peak"] else "–"
        L.append(f"| {d['bs']} | {d['secs'] / d['frames']:.2f}초 ({d['frames']}장 {d['secs'] / 60:.1f}분) | {peak} | "
                 f"{same}/{total} ({same / total * 100:.0f}%) | {sum(sims) / len(sims):.3f} |")
    L += ["", "검색 결과 (각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / R@3, 개수):", "",
          "| 방식 | 묶음 | 전체 | S | V |", "|---|---|---|---|---|"]
    for key, label in METHODS:
        fn = summary.by_key(key)
        for d in data:
            cells = []
            for typ in (None, "S", "V"):
                rs = [r for r in d["rows"] if typ is None or r["type"] == typ]
                v = [fn(r) for r in rs]
                cells.append(f"{sum(x[1] for x in v):.0f} / {sum(x[2] for x in v):.0f} / {sum(x[3] for x in v):.0f} (n={len(rs)})")
            L.append(f"| {label} | {d['bs']} | " + " | ".join(cells) + " |")
    L += ["", "## 해석", "", INTERPRETATION, "",
          "## 재현 방법", "",
          "    OUT=~/scenefinder_eval/results_v2_b4_dev   # feature·자막·labels_snapshot.json은 results_v2에서 복사",
          "    python ai/experiments/translation_compare/captions.py --out $OUT --queries $OUT/labels_snapshot.json --subset dev --variants qwen_incl --batch-size 4",
          "    python ai/experiments/translation_compare/run.py --out $OUT --queries $OUT/labels_snapshot.json --subset dev",
          "    python ai/experiments/translation_compare/fusion.py --out $OUT",
          "    python ai/experiments/translation_compare/caption_batch_compare.py --runs 1=~/scenefinder_eval/results_v2 4=$OUT 8=~/scenefinder_eval/results_v2_b8", ""]
    Path(args.output).write_text("\n".join(L), encoding="utf-8")
    print("작성:", args.output)


if __name__ == "__main__":
    main()
