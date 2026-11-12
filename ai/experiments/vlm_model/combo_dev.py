"""N3 VLM 버전 결합 규칙을 dev에서 정한다 (vlm_model_plan.md 4장 「N3의 결합 규칙 후보」, 11/20~22 작업).

후보 구간 풀 → 구간마다 세 점수 → 가중합으로 다시 순위:
  - s_sub  : 자막 검색 B1(파인튜닝 MiniLM) — 구간과 겹치는 자막 창 중 최고 점수, 영상 안 z 정규화
  - s_frame: 화면 검색 N2(Qwen3-VL-Emb, 무학습 또는 고른 LoRA) — 구간 칸들의 평활 점수 평균, 영상 안 z 정규화
  - s_mr   : 구간 검색 VLM 버전 N1 — 그 구간과 IoU≥0.5인 N1 후보의 순위 점수 1/(1+순위), 없으면 0
규칙 후보 (계획 그대로 두 가지):
  (2) rerank : 풀 = B1 상위 K + N1 상위 3 → 화면 점수로 다시 매김 (VLM 장면 재판별)
  (1) fusion : 풀 = B1 상위 K + N1 상위 3 + N2 상위 3 구간 → 세 점수 가중합
고르기: dev 전체 R@1 IoU≥0.3 최대, 동점이면 R@3, 시작 ±5초. 격자가 작아도 질의 80개에 맞춘 것이라 test에서 확인 필요(보고서에 적음).

    python ai/experiments/vlm_model/combo_dev.py dump --frame zero|lora   # GPU, 신호 저장
    python ai/experiments/vlm_model/combo_dev.py grid                     # CPU
"""
import argparse, itertools, json, sys
from pathlib import Path

import torch

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "ai/experiments/translation_compare")]
OUT = HERE / "results/combo_dev"
MR_ROWS = Path("/nfs/team/data/scenefinder_vlm/mr_runs/dev_eval_win/w45_s23/rows.json")
LORA_SEL = Path("/nfs/team/data/scenefinder_vlm/lora_runs/selected.json")
N1_NAME = "vlm_tok_ko"


def dump(a):
    import prelim_eval as pe
    if a.frame == "lora":
        sel = json.loads(LORA_SEL.read_text())
        if sel["selected"]:
            ad = sel["candidates"][sel["selected"]]["adapter"]
            pe.LORA["adapter"] = ad; pe.LORA["feats"] = str(Path(ad).parent / "dev_qwen_640")
    videos, pos, neg, _ = pe.load_queries(include_unreviewed=False)
    dev = {k: v for k, v in videos.items() if v["split"] == "dev"}
    assert all(q["video"] in dev for q in pos + neg)
    m = pe.Methods(dev)
    mr = {r["num"]: r for r in json.loads(MR_ROWS.read_text())}
    sig = []
    for q in pos + neg:
        k = q["video"]
        qv = m._qwen_text([q["query"]], pe.QWEN_Q_INSTR)[0]
        fs = m.smooth(m._feat(k, "qwen_640") @ qv)
        frame_spans, _ = m._frame_rank(k, qv, "qwen_640")
        sig.append({"num": q["num"], "video": k, "is_neg": not q.get("gt"), "gt": q.get("gt"), "type": q.get("type"),
                    "origin": q["origin"], "overlay_text": bool(q.get("overlay_text")), "duration": dev[k]["duration"],
                    "sub": m._sub_ranked(k, q["query"]),               # [(s, e, score)] 점수순 (원래 자막 창)
                    "frame_bins": fs.tolist(), "frame_spans": frame_spans[:4],
                    "mr_top5": mr[q["num"]][N1_NAME]["top5"] if q["num"] in mr else []})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"signals_{a.frame}.json").write_text(json.dumps({"frame": a.frame, "lora": pe.LORA["adapter"], "rows": sig}, ensure_ascii=False))
    print(f"→ {OUT}/signals_{a.frame}.json ({len(sig)}개)")


def z(xs):
    t = torch.tensor(xs, dtype=torch.float32)
    return ((t - t.mean()) / (t.std() + 1e-6)).tolist() if len(xs) > 1 else [0.0] * len(xs)


def rank_query(r, rule, K, w_frame, w_mr, widen, shift=0.0):
    import summary
    subs = r["sub"]; fb = r["frame_bins"]; fz = z(fb)
    sz = z([s[2] for s in subs]) if subs else []
    pool = [widen(s[:2]) for s in subs[:K]] + [tuple(x) for x in r["mr_top5"][:3]]
    if rule == "fusion":
        pool += [(max(0.0, x[0] - shift), x[1]) for x in r["frame_spans"][:3]]   # 화면 검색 구간만 시작 앞당김
    if not pool:
        return [], None

    def s_sub(c):
        ov = [sz[i] for i, s in enumerate(subs) if min(c[1], s[1]) - max(c[0], s[0]) > 0]
        return max(ov) if ov else (min(sz) if sz else 0.0)

    def s_frame(c):
        b0, b1 = int(c[0] // 2), max(int(c[0] // 2) + 1, int(-(-c[1] // 2)))
        seg = fz[b0:min(b1, len(fz))]
        return sum(seg) / len(seg) if seg else min(fz)

    def s_mr(c):
        for i, x in enumerate(r["mr_top5"]):
            if summary.iou(c, tuple(x)) >= 0.5:
                return 1.0 / (1 + i)
        return 0.0

    w_sub = 1.0 if subs else 0.0
    scored = [(w_sub * s_sub(c) + w_frame * s_frame(c) + w_mr * s_mr(c), c) for c in pool]
    scored.sort(key=lambda x: -x[0])
    return summary.nms_top([c for _, c in scored], k=5), scored[0][0]


def grid(a):
    import summary
    from prelim_eval import widen
    out = {}
    for frame in ("zero", "lora"):
        p = OUT / f"signals_{frame}.json"
        if not p.exists():
            continue
        rows = [r for r in json.loads(p.read_text())["rows"] if r["gt"]]
        res = []
        grid_ = [(ru, K, wf, wm, sh) for ru, K, wf, wm, sh in itertools.product(("rerank", "fusion"), (5, 10), (0.0, 0.25, 0.5, 1.0, 2.0),
                                                                              (0.0, 0.5), (0.0, 2.0, 4.0))
                 if ru == "fusion" or sh == 0.0]   # rerank 풀에는 화면 검색 구간이 없어 앞당기기 해당 없음
        for rule, K, wf, wm, sh in grid_:
            r1 = r3 = st = 0
            for r in rows:
                top, _ = rank_query(r, rule, K, wf, wm, widen, sh)
                if not top:
                    continue
                r1 += summary.best_iou(top[0], r["gt"]) >= 0.3
                r3 += any(summary.best_iou(c, r["gt"]) >= 0.3 for c in top[:3])
                st += summary.start_ok(top[0], r["gt"]) if hasattr(summary, "start_ok") else 0
            res.append({"frame": frame, "rule": rule, "K": K, "w_frame": wf, "w_mr": wm, "shift": sh, "r1": r1, "r3": r3, "start5": st, "n": len(rows)})
        res.sort(key=lambda x: (-x["r1"], -x["r3"], -x["start5"]))
        out[frame] = res
        print(f"[{frame}] 상위 5:")
        for x in res[:5]:
            print("  ", x)
        base = next(x for x in res if x["rule"] == "rerank" and x["K"] == 5 and x["w_frame"] == 0 and x["w_mr"] == 0)
        print("   (B1 순서 그대로:", base, ")")
    (OUT / "grid.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    # 화면 점수 종류까지 포함해 같은 기준으로 하나 고르고, 그 규칙의 질의별 결과를 저장 (보조 지표·정답 없음 임계값용)
    best = sorted([x for v in out.values() for x in v], key=lambda x: (-x["r1"], -x["r3"], -x["start5"]))[0]
    sig = json.loads((OUT / f"signals_{best['frame']}.json").read_text())["rows"]
    rows, negs = [], []
    for r in sig:
        top, sc = rank_query(r, best["rule"], best["K"], best["w_frame"], best["w_mr"], widen, best["shift"]) or ([], None)
        if not r["gt"]:
            negs.append({"num": r["num"], "video": r["video"], "origin": r["origin"], "N3": sc}); continue
        rows.append({k: r[k] for k in ("num", "video", "type", "origin", "overlay_text", "gt")} |
                    {"N3": {"top5": top, "iou": summary.best_iou(top[0], r["gt"]) if top else 0.0, "score": sc}})
    (OUT / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (OUT / "negatives.json").write_text(json.dumps(negs, ensure_ascii=False, indent=1))
    (OUT / "selected.json").write_text(json.dumps(best, ensure_ascii=False, indent=1))
    print("고른 규칙:", best)


def no_n1(a):
    """2026-11-12 사용자 결정: 시간 한도(특징 추출 1.5초/영상 1분) 때문에 N1 후보를 풀에서 뺀 N3.
    고른 규칙의 나머지(화면 점수 LoRA, K, 가중치, 앞당기기)는 그대로 두고 다시 고르지 않는다."""
    import summary
    from prelim_eval import widen
    best = json.loads((OUT / "selected.json").read_text())
    sig = json.loads((OUT / f"signals_{best['frame']}.json").read_text())["rows"]
    out = OUT.parent / "combo_dev_noN1"; out.mkdir(parents=True, exist_ok=True)
    rows, negs = [], []
    for r in sig:
        r = {**r, "mr_top5": []}
        top, sc = rank_query(r, best["rule"], best["K"], best["w_frame"], best["w_mr"], widen, best["shift"])
        if not r["gt"]:
            negs.append({"num": r["num"], "video": r["video"], "origin": r["origin"], "N3": sc}); continue
        rows.append({k: r[k] for k in ("num", "video", "type", "origin", "overlay_text", "gt")} |
                    {"N3": {"top5": top, "iou": summary.best_iou(top[0], r["gt"]), "score": sc}})
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (out / "negatives.json").write_text(json.dumps(negs, ensure_ascii=False, indent=1))
    (out / "selected.json").write_text(json.dumps({**best, "n1_in_pool": False, "note": "시간 한도 때문에 N1 후보 제외(2026-11-12 사용자 결정)"}, ensure_ascii=False, indent=1))
    sig_out = json.loads((OUT / f"signals_{best['frame']}.json").read_text())
    for r in sig_out["rows"]:
        r["mr_top5"] = []
    (out / f"signals_{best['frame']}.json").write_text(json.dumps(sig_out, ensure_ascii=False))
    print("N1 후보 없는 N3:", sum(r["N3"]["iou"] >= 0.3 for r in rows), "/", len(rows), "→", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dump", "grid", "no_n1"]); ap.add_argument("--frame", choices=["zero", "lora"], default="zero")
    a = ap.parse_args()
    {"dump": dump, "grid": grid, "no_n1": no_n1}[a.cmd](a)


if __name__ == "__main__":
    main()
