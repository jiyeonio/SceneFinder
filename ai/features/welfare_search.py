"""복지바로봄 장면 검색 엔진 (시연 영상 세트, 미리 분석한 색인에서 검색).

방식 (SEARCH_MODEL)
  - n3     : 자막 MiniLM(파인튜닝) 상위 5 + LoRA 화면 검색 상위 3(시작 4초 앞당김), 점수 = z(자막) + 0.25 × z(화면)
             (평가에서 고른 N3, N1 후보 없음 — docs/experiments/vlm_model_plan.md, 결합 함수는 평가 코드 그대로 import)
  - n3_vlm : n3 상위 5개를 로컬 Qwen3-VL-4B가 다시 판별(프롬프트 A 「답하는가」, mix 결합) + 상위 3개 화면 확인(프롬프트 B) → verification
  - main   : 기존 서비스 방식(backend/services/search_api.predict_moments)은 search_api 쪽에서 처리
verification: 'screen'(화면에서 확인됨: B ≥ 0.5) / 'subtitle'(자막에서 확인됨: A ≥ 0.5, B < 0.5) / 'none'(확인 안 됨) / 'pending'(확인 중)
※ verification 임계값 0.5는 dev에서 맞추지 않은 값입니다.
"""
import json, os, sys, threading
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "ai/experiments/vlm_model")]
D = Path(os.environ.get("WELFARE_DATA_DIR", "/nfs/team/data/scenefinder_vlm"))
IDX = D / "demo/index"
LORA_ADAPTER = D / "lora_runs/welfare/ep1/adapter.pt"
CATALOG = ROOT / "backend/data/demo_videos.json"
COMBO = json.loads((ROOT / "ai/experiments/vlm_model/results/combo_dev_noN1/selected.json").read_text())
Q_INSTR = "Retrieve images or video frames relevant to the user's query."
PAD_BEFORE, MIN_LEN = 2.0, 6.0
CLIP_LEN = 2
RERANK_K = 5
VERIFY_TOP = 3
JUDGE_MODEL = "Qwen/Qwen3-VL-4B-Instruct"
PROMPT_A = ("질문: {q}\n\n위 이미지 3장은 영상의 한 장면(앞·가운데·뒤)이고, 아래는 이 장면의 자막입니다.\n자막: {sub}\n\n"
            "이 장면(화면과 자막)이 질문에 직접 답합니까? 예 또는 아니오로만 답하세요.")
PROMPT_B = ("질문: {q}\n\n위 이미지 3장은 영상의 한 장면(앞·가운데·뒤)이고, 아래는 이 장면의 자막입니다.\n자막: {sub}\n\n"
            "질문이 찾는 내용이 이 장면의 화면에 실제로 보입니까? 자막에서 말로만 언급되면 아니오입니다. 예 또는 아니오로만 답하세요.")


def widen(seg):   # 서비스 자막 구간 보정 (prelim_eval.widen과 같음)
    s = max(0.0, seg[0] - PAD_BEFORE)
    return (round(s, 2), round(max(seg[1], s + MIN_LEN), 2))


class WelfareSearch:
    def __init__(self, use_vlm=True):
        from sentence_transformers import SentenceTransformer
        import speed_opt
        from lora import load_lora
        from ai.features.run_moment_detr_inference import VISUAL_TOP_K, _make_contiguous_clusters, _smooth_scores
        self.topk_bins, self.clusters, self.smooth = VISUAL_TOP_K, _make_contiguous_clusters, _smooth_scores
        self.catalog = {v["youtube_id"]: v for v in json.loads(CATALOG.read_text())}
        self.minilm = SentenceTransformer(os.environ["SCENEFINDER_MINILM_MODEL_PATH"])
        self.emb = speed_opt.Embedder(); load_lora(self.emb.m, LORA_ADAPTER)
        self.proc = self.emb.proc["torchvision"]
        self._v = {}
        self.judge = Judge() if use_vlm else None
        self.lock = threading.Lock()   # GPU는 한 번에 한 요청

    # ---------- 색인 ----------
    def video(self, yid):
        if yid not in self._v:
            d = IDX / yid
            segs = json.loads((d / "subs.json").read_text())["segments"]
            wins = [(segs[i]["start_time"], segs[i + s - 1]["end_time"], " ".join(x["text"] for x in segs[i:i + s]))
                    for s in (1, 2, 3) for i in range(len(segs) - s + 1)]
            we = self.minilm.encode([w[2] for w in wins], convert_to_tensor=True) if wins else None
            feats = F.normalize(torch.load(d / "lora_640.pt", map_location="cpu").float(), dim=-1)
            self._v[yid] = {"segs": segs, "wins": wins, "win_emb": we, "feats": feats,
                            "frames": np.load(d / "frames.npy", mmap_mode="r"), "duration": float(self.catalog[yid]["duration_sec"])}
        return self._v[yid]

    @torch.no_grad()
    def encode(self, q):
        mq = self.minilm.encode(q, convert_to_tensor=True)
        msgs = [[{"role": "system", "content": [{"type": "text", "text": Q_INSTR}]}, {"role": "user", "content": [{"type": "text", "text": q}]}]]
        x = self.proc(text=self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False), padding=True, return_tensors="pt").to("cuda")
        h = self.emb.m(**x).last_hidden_state
        qv = F.normalize(h[0, x["attention_mask"].sum(1)[0] - 1].float(), dim=-1).cpu()
        return mq, qv

    # ---------- N3 (평가 코드와 같은 계산) ----------
    def _sub_ranked(self, v, mq):
        if not v["wins"]:
            return []
        from sentence_transformers import util
        sc = util.cos_sim(mq, v["win_emb"])[0]
        order = sc.argsort(descending=True).tolist()
        return [(float(v["wins"][i][0]), float(v["wins"][i][1]), round(sc[i].item(), 4)) for i in order]

    def _frame_rank(self, v, qv):
        sm = self.smooth(v["feats"] @ qv)
        dur = v["duration"]
        top = torch.topk(sm, k=min(self.topk_bins, len(sm))).indices.tolist()
        multi = [c for c in self.clusters(top) if len(c) >= 2]
        span = lambda c: (float(min(c) * CLIP_LEN), float(min((max(c) + 1) * CLIP_LEN, dur)))  # noqa: E731
        ranked = sorted(multi, key=lambda c: (len(c), float(sm[c].mean())), reverse=True)
        best = ranked[0] if ranked else [int(torch.argmax(sm))]
        ranked += [[i] for i in torch.argsort(sm, descending=True).tolist()]
        return [span(best)] + [span(c) for c in ranked], sm

    def n3(self, yid, mq, qv):
        from combo_dev import rank_query
        v = self.video(yid)
        subs = self._sub_ranked(v, mq)
        spans_f, sm = self._frame_rank(v, qv)
        sig = {"sub": subs, "frame_bins": sm.tolist(), "frame_spans": spans_f[:4], "mr_top5": []}
        top, score = rank_query(sig, COMBO["rule"], COMBO["K"], COMBO["w_frame"], COMBO["w_mr"], widen, COMBO["shift"])
        raw_sub = max((s[2] for s in subs), default=0.0)          # 영상 간 비교용(검증 안 된 값)
        raw_frame = float(sm.max()) if len(sm) else 0.0
        return {"top": [tuple(x) for x in top[:RERANK_K]], "score": score, "raw_sub": raw_sub, "raw_frame": raw_frame}

    def subtitle_text(self, yid, span, limit=200):
        v = self.video(yid); s, e = span
        return " ".join(x["text"].strip() for x in v["segs"] if x["end_time"] > s and x["start_time"] < e)[:limit]

    # ---------- VLM 재판별 ----------
    def rejudge(self, yid, q, top):
        v = self.video(yid)
        inputs = [self.judge.inputs(v["frames"], self.subtitle_text(yid, sp), sp) for sp in top]
        pa = self.judge.p_yes(q, inputs, PROMPT_A)
        k = len(top)
        mix = [0.5 * (1 - i / (k - 1) if k > 1 else 1.0) + 0.5 * pa[i] for i in range(k)]
        order = sorted(range(k), key=lambda i: -mix[i])
        new = [top[i] for i in order]; pa_new = [pa[i] for i in order]
        pb = self.judge.p_yes(q, [inputs[i] for i in order[:VERIFY_TOP]], PROMPT_B)
        ver = ["screen" if b >= 0.5 else ("subtitle" if a >= 0.5 else "none") for a, b in zip(pa_new[:VERIFY_TOP], pb)]
        return {"top": new, "p_answer": pa_new, "p_screen": pb, "verification": ver}


class Judge:
    def __init__(self):
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.proc = AutoProcessor.from_pretrained(JUDGE_MODEL); self.proc.tokenizer.padding_side = "left"
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(JUDGE_MODEL, dtype=torch.bfloat16).cuda().eval()
        tok = self.proc.tokenizer
        self.yes, self.no = tok.encode("예", add_special_tokens=False)[0], tok.encode("아니오", add_special_tokens=False)[0]

    @staticmethod
    def inputs(frames, sub, span):
        s, e = span; n = len(frames)
        ts = [min(s + 1, (s + e) / 2), (s + e) / 2, max(e - 1, (s + e) / 2)]
        return [np.asarray(frames[min(n - 1, max(0, int(t // CLIP_LEN)))]) for t in ts], sub or "(없음)"

    @torch.no_grad()
    def p_yes(self, q, inputs, prompt):
        from PIL import Image
        if not inputs:
            return []
        msgs, imgs = [], []
        for im, sub in inputs:
            imgs += [Image.fromarray(x) for x in im]
            msgs.append([{"role": "user", "content": [{"type": "image"}] * 3 + [{"type": "text", "text": prompt.format(q=q, sub=sub)}]}])
        x = self.proc(text=self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False),
                      images=imgs, padding=True, return_tensors="pt").to("cuda")
        lg = self.model(**x).logits[:, -1, :].float()
        return torch.softmax(torch.stack([lg[:, self.yes], lg[:, self.no]], 1), 1)[:, 0].tolist()
