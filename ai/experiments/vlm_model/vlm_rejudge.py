"""VLM 장면 재판별 (제안서 3-가-③) — dev에서 후보 비교와 지연 측정. 설정은 vlm_model_plan.md 「VLM 장면 재판별」에 결과 전 고정.

N3 상위 K개 후보 구간마다 프레임 3장(시작+1초·가운데·끝−1초의 2초 칸) + 구간 자막을 로컬 Qwen3-VL-4B-Instruct에 넣고,
첫 응답 토큰의 「예」 vs 「아니오」(첫 토큰) logit으로 P(예)를 구한다(생성 없이 forward 한 번, 후보 K개를 한 묶음).
  score   : K=5, 프롬프트 A·B 모두 P(예) 계산 → <out>/scores.json  (K=3은 앞 3개를 그대로 씀)
  latency : 서비스와 같은 순서로 질의당 ① N3 기본 결과 ② + VLM 재판별(K=3·5, 프롬프트별)을 잼 (두 모델을 GPU에 함께 올림)
  grid    : 후보 8개 + 재판별 없음 비교, 고른 설정의 질의별 결과·보조 지표 → <out>/grid.json, rows.json, selected.json
dev만 다룬다(test 영상·질의는 이 스크립트로 돌릴 수 없음).

    python ai/experiments/vlm_model/vlm_rejudge.py frames|score|latency|grid
"""
import argparse, itertools, json, statistics, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(HERE), str(ROOT / "ai/experiments/translation_compare")]
D = Path("/nfs/team/data/scenefinder_vlm")
FRAMES = D / "eval_frames_640"
OUT = HERE / "results/vlm_rejudge_dev"
COMBO = HERE / "results/combo_dev"
# --pool noN1: 시간 한도 때문에 N1 후보를 뺀 N3 풀 (2026-11-12 사용자 결정)
POOLS = {"withN1": (HERE / "results/combo_dev", HERE / "results/vlm_rejudge_dev"),
         "noN1": (HERE / "results/combo_dev_noN1", HERE / "results/vlm_rejudge_dev_noN1")}
MODEL = "Qwen/Qwen3-VL-4B-Instruct"
CLIP_LEN = 2
KMAX = 5
PROMPTS = {
    "A": "질문: {q}\n\n위 이미지 3장은 영상의 한 장면(앞·가운데·뒤)이고, 아래는 이 장면의 자막입니다.\n자막: {sub}\n\n"
         "이 장면(화면과 자막)이 질문에 직접 답합니까? 예 또는 아니오로만 답하세요.",
    "B": "질문: {q}\n\n위 이미지 3장은 영상의 한 장면(앞·가운데·뒤)이고, 아래는 이 장면의 자막입니다.\n자막: {sub}\n\n"
         "질문이 찾는 내용이 이 장면의 화면에 실제로 보입니까? 자막에서 말로만 언급되면 아니오입니다. 예 또는 아니오로만 답하세요.",
}


def dev_videos():
    labels = json.loads((HERE / "labels/review.json").read_text())
    v = {k: x for k, x in labels["videos"].items() if x["split"] == "dev"}
    assert v and all(x["split"] == "dev" for x in v.values())
    return v


def cmd_frames(a):
    """dev 영상 2초 칸 프레임 저장 (서비스 색인 때 저장하는 것과 같음). 칸 수는 평가 특징과 맞춤."""
    import speed_opt
    FRAMES.mkdir(parents=True, exist_ok=True)
    for k, v in dev_videos().items():
        f = FRAMES / f"{v['youtube_id']}.npy"
        if f.exists():
            continue
        n = len(torch.load(D / "eval_features/clip" / f"{v['youtube_id']}_clip_features.pt"))
        np.save(f, speed_opt.decode(D / "eval_videos" / f"{v['youtube_id']}.mp4", n, "cpu"))
        print(k, n, flush=True)


class Judge:
    def __init__(self):
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.proc = AutoProcessor.from_pretrained(MODEL); self.proc.tokenizer.padding_side = "left"
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16).cuda().eval()
        tok = self.proc.tokenizer
        self.yes, self.no = tok.encode("예", add_special_tokens=False)[0], tok.encode("아니오", add_special_tokens=False)[0]
        assert self.yes != self.no
        self.frames, self.subs = {}, {}

    def _frames(self, yid):
        if yid not in self.frames:
            self.frames[yid] = np.load(FRAMES / f"{yid}.npy", mmap_mode="r")
            self.subs[yid] = json.loads((D / "eval_subtitles" / f"{yid}.json").read_text())["segments"]
        return self.frames[yid], self.subs[yid]

    def inputs(self, yid, span):
        fr, subs = self._frames(yid)
        s, e = span; n = len(fr)
        ts = [min(s + 1, (s + e) / 2), (s + e) / 2, max(e - 1, (s + e) / 2)]
        imgs = [np.asarray(fr[min(n - 1, max(0, int(t // CLIP_LEN)))]) for t in ts]
        text = " ".join(x["text"].strip() for x in subs if x["end_time"] > s and x["start_time"] < e)[:200] or "(없음)"
        return imgs, text

    @torch.no_grad()
    def p_yes(self, q, yid, spans, prompt):
        from PIL import Image
        msgs, imgs = [], []
        for sp in spans:
            im, sub = self.inputs(yid, sp)
            imgs += [Image.fromarray(x) for x in im]
            msgs.append([{"role": "user", "content": [{"type": "image"}] * 3 + [{"type": "text", "text": PROMPTS[prompt].format(q=q, sub=sub)}]}])
        text = self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        x = self.proc(text=text, images=imgs, padding=True, return_tensors="pt").to("cuda")
        logits = self.model(**x).logits[:, -1, :].float()
        two = torch.stack([logits[:, self.yes], logits[:, self.no]], 1)
        return torch.softmax(two, 1)[:, 0].tolist()


def load_n3():
    rows = json.loads((COMBO / "rows.json").read_text())
    sig = {r["num"]: r for r in json.loads((COMBO / "signals_lora.json").read_text())["rows"]}
    labels = json.loads((HERE / "labels/review.json").read_text())
    qtext = {q["num"]: q for q in labels["queries"] + labels.get("negative_queries", [])}
    return rows, sig, qtext


def cmd_score(a):
    vids = dev_videos(); rows, _, qtext = load_n3()
    j = Judge(); out = {}
    for r in rows:
        q = qtext[r["num"]]; yid = vids[r["video"]]["youtube_id"]
        spans = [tuple(x) for x in r["N3"]["top5"][:KMAX]]
        out[r["num"]] = {"spans": spans, **{p: j.p_yes(q["query"], yid, spans, p) for p in PROMPTS}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scores.json").write_text(json.dumps({"model": MODEL, "scores": out}, ensure_ascii=False, indent=1))
    print(f"→ {OUT}/scores.json ({len(out)}개)")


def cmd_latency(a):
    """서비스 순서 그대로: MiniLM 자막 후보 + LoRA 화면 검색 + 결합(N3) → VLM 재판별. 질의 문장만 입력으로 받음."""
    import prelim_eval as pe, combo_dev
    sel = json.loads((D / "lora_runs/selected.json").read_text())
    ad = sel["candidates"][sel["selected"]]["adapter"]
    pe.LORA["adapter"] = ad; pe.LORA["feats"] = str(Path(ad).parent / "dev_qwen_640")
    best = json.loads((COMBO / "selected.json").read_text())
    videos, pos, neg, _ = pe.load_queries(include_unreviewed=False)
    vids = {k: v for k, v in videos.items() if v["split"] == "dev"}
    m = pe.Methods(vids); j = Judge()
    qs = pos + neg
    # 예열 (첫 호출 초기화 제외)
    for q in qs[:3]:
        sig = {"sub": m._sub_ranked(q["video"], q["query"])}; qv = m._qwen_text([q["query"]], pe.QWEN_Q_INSTR)[0]
        j.p_yes(q["query"], vids[q["video"]]["youtube_id"], [(0, 10)] * 5, "A")
    lat = {"base": [], **{f"K{k}_{p}": [] for k in (3, 5) for p in PROMPTS}}
    torch.cuda.reset_peak_memory_stats()
    for q in qs:
        k_ = q["video"]; yid = vids[k_]["youtube_id"]
        torch.cuda.synchronize(); t0 = time.time()
        qv = m._qwen_text([q["query"]], pe.QWEN_Q_INSTR)[0]
        fs = m.smooth(m._feat(k_, "qwen_640") @ qv)
        spans_f, _ = m._frame_rank(k_, qv, "qwen_640")
        sig = {"sub": m._sub_ranked(k_, q["query"]), "frame_bins": fs.tolist(), "frame_spans": spans_f[:4], "mr_top5": []}
        top, _ = combo_dev.rank_query(sig, best["rule"], best["K"], best["w_frame"], best["w_mr"], pe.widen, best["shift"])
        torch.cuda.synchronize(); tb = time.time() - t0
        lat["base"].append(tb)
        for k in (3, 5):
            for p in PROMPTS:
                torch.cuda.synchronize(); t1 = time.time()
                j.p_yes(q["query"], yid, [tuple(x) for x in top[:k]], p)
                torch.cuda.synchronize(); lat[f"K{k}_{p}"].append(tb + time.time() - t1)
    pct = lambda v, p: sorted(v)[int(p * (len(v) - 1))]  # noqa: E731
    res = {n: {"p50": round(statistics.median(v), 3), "p95": round(pct(v, 0.95), 3), "max": round(max(v), 3)} for n, v in lat.items()}
    res["note"] = "base = N3 기본 결과(질의 인코딩·자막 후보·화면 검색·결합). K*_* = 기본 결과 + VLM 재판별 완료까지. 프레임은 미리 저장한 2초 칸 프레임 읽기(디코딩 제외)."
    res["n_queries"] = len(qs); res["gpu_peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latency.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


def rerank(spans, py, K, comb):
    k = min(K, len(spans))
    head = list(range(k))
    if comb == "vlm_only":
        sc = {i: py[i] for i in head}
    else:
        sc = {i: 0.5 * (1 - i / (k - 1) if k > 1 else 1.0) + 0.5 * py[i] for i in head}
    order = sorted(head, key=lambda i: -sc[i]) + list(range(k, len(spans)))
    return [spans[i] for i in order]


def cmd_grid(a):
    import summary
    rows, sig, _ = load_n3()
    S = json.loads((OUT / "scores.json").read_text())["scores"]
    labels = json.loads((HERE / "labels/review.json").read_text())
    subonly = {q["num"]: q["subtitle_only_spans"] for q in labels["queries"] if q.get("subtitle_only_spans")}

    def evaluate(get):
        res = {"r1": 0, "r3": 0, "start5": 0, "early": 0, "user_r1": 0, "user_r3": 0, "subonly_hit": 0, "subonly_n": 0,
               "v_wrong_subonly": 0, "v_n": 0}
        per = []
        for r in rows:
            top = get(r)
            ok1 = summary.best_iou(top[0], r["gt"]) >= 0.3
            ok3 = any(summary.best_iou(c, r["gt"]) >= 0.3 for c in top[:3])
            d = min((g[0] - top[0][0] for g in r["gt"]), key=abs)
            res["r1"] += ok1; res["r3"] += ok3; res["start5"] += abs(d) <= 5; res["early"] += 0 <= d <= 5
            if r["origin"] == "simulated_user":
                res["user_r1"] += ok1; res["user_r3"] += ok3
            if r["num"] in subonly:
                res["subonly_n"] += 1; res["subonly_hit"] += summary.best_iou(top[0], subonly[r["num"]]) >= 0.3
            if r["type"] == "V":
                res["v_n"] += 1
                fs = [tuple(x) for x in sig[r["num"]]["frame_spans"][:3]]
                from_frames = any(summary.iou(top[0], (max(0.0, f[0] - 4.0), f[1])) >= 0.5 or summary.iou(top[0], f) >= 0.5 for f in fs)
                res["v_wrong_subonly"] += (not ok1) and not from_frames
            per.append({k: r[k] for k in ("num", "video", "type", "origin", "overlay_text", "gt")} |
                       {"top5": top[:5], "iou": summary.best_iou(top[0], r["gt"])})
        return res, per

    grid = []
    base, base_rows = evaluate(lambda r: [tuple(x) for x in r["N3"]["top5"]])
    grid.append({"name": "N3 (재판별 없음)", "K": 0, "prompt": None, "comb": None, **base})
    per_cfg = {"N3 (재판별 없음)": base_rows}
    for K, p, comb in itertools.product((3, 5), ("A", "B"), ("vlm_only", "mix")):
        name = f"K{K}_{p}_{comb}"
        res, per = evaluate(lambda r: rerank([tuple(x) for x in S[str(r["num"])]["spans"]], S[str(r["num"])][p], K, comb))
        grid.append({"name": name, "K": K, "prompt": p, "comb": comb, **res}); per_cfg[name] = per
    order = sorted(grid, key=lambda x: (-x["r1"], -x["r3"], -x["start5"], x["K"]))
    best = order[0]
    (OUT / "grid.json").write_text(json.dumps(grid, ensure_ascii=False, indent=1))
    (OUT / "rows.json").write_text(json.dumps([{**x, "N3VLM": {"top5": x["top5"], "iou": x["iou"]}} for x in per_cfg[best["name"]]],
                                              ensure_ascii=False, indent=1))
    final = "N3+VLM 재판별" if best["K"] and best["r1"] > base["r1"] + 3 else "N3"
    (OUT / "selected.json").write_text(json.dumps({"selected": best, "n3": base, "final_candidate_rule": "고른 설정이 N3보다 R@1 3개 넘게 높으면 N3+VLM",
                                                   "final_candidate": final}, ensure_ascii=False, indent=1))
    print("이름                 R@1 R@3 시작±5 앞0~5 | 사용자 R@1 R@3 | 자막만표시 1위겹침 | V오답·자막후보만")
    for x in grid:
        print(f"{x['name']:20s} {x['r1']:3d} {x['r3']:3d} {x['start5']:5d} {x['early']:5d} | {x['user_r1']:6d} {x['user_r3']:3d} | "
              f"{x['subonly_hit']}/{x['subonly_n']} | {x['v_wrong_subonly']}/{x['v_n']}")
    print("고름:", best["name"], "→ 최종 후보:", final)


def main():
    global COMBO, OUT
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["frames", "score", "latency", "grid"])
    ap.add_argument("--pool", choices=list(POOLS), default="withN1")
    a = ap.parse_args()
    COMBO, OUT = POOLS[a.pool]
    {"frames": cmd_frames, "score": cmd_score, "latency": cmd_latency, "grid": cmd_grid}[a.cmd](a)


if __name__ == "__main__":
    main()
