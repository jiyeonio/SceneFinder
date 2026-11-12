"""화면 검색 LoRA 설정 고르기 (vlm_model_plan.md 「고르는 기준(dev, 결과 보기 전 고정)」 그대로).

- 점수 = dev 사용자 질문(정답 있음)의 R@1 IoU≥0.3 개수 + R@3 개수
- 탈락: dev AI 초안 질의의 R@1 IoU≥0.3이 무학습(F-VLM 예비 실험)보다 3개 넘게 적음
- 무학습도 후보로 같이 표시(점수 비교용)

    python ai/experiments/vlm_model/lora_select.py --runs /nfs/team/data/scenefinder_vlm/lora_runs --out <json>
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "experiments/translation_compare"))
import summary


def stats(rows, m="F-VLM"):
    user = [r for r in rows if r["origin"] == "simulated_user"]; ai = [r for r in rows if r["origin"] != "simulated_user"]
    r1 = lambda rs: sum(r[m]["iou"] >= 0.3 for r in rs)  # noqa: E731
    r3 = lambda rs: sum(any(summary.best_iou(s, r["gt"]) >= 0.3 for s in r[m]["top5"][:3]) for r in rs)  # noqa: E731
    return {"user_r1": r1(user), "user_r3": r3(user), "n_user": len(user), "ai_r1": r1(ai), "n_ai": len(ai), "all_r1": r1(rows), "n": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    zero = stats(json.loads((HERE / "results/prelim_dev/rows.json").read_text()))
    zero["score"] = zero["user_r1"] + zero["user_r3"]
    cands = {"zero_shot": {**zero, "eliminated": False}}
    for f in sorted(Path(a.runs).glob("*/ep*/dev_eval/rows.json")):
        name = f"{f.parts[-4]}_{f.parts[-3]}"
        s = stats(json.loads(f.read_text()))
        s["score"] = s["user_r1"] + s["user_r3"]
        s["eliminated"] = s["ai_r1"] < zero["ai_r1"] - 3
        s["adapter"] = str(f.parent.parent / "adapter.pt")
        cands[name] = s
    ok = {k: v for k, v in cands.items() if k != "zero_shot" and not v["eliminated"]}
    best = max(ok, key=lambda k: (ok[k]["score"], ok[k]["all_r1"])) if ok else None
    out = {"rule": "user R@1+R@3 최대, AI 초안 R@1이 무학습보다 3개 넘게 떨어지면 탈락 (동점이면 전체 R@1)",
           "selected": best, "candidates": cands}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k, v in cands.items():
        print(f"{k:14s} 사용자 R@1 {v['user_r1']}/{v['n_user']} R@3 {v['user_r3']} 점수 {v['score']} | AI 초안 R@1 {v['ai_r1']}/{v['n_ai']} "
              f"| 전체 {v['all_r1']}/{v['n']}{' 탈락' if v['eliminated'] else ''}")
    print("고름:", best)


if __name__ == "__main__":
    main()
