"""Qwen3-VL-Embedding-2B 질의 텍스트 특징 (구간 검색 모델 VLM 버전의 질의 입력). 두 가지를 같이 만든다:

- tok: 지시문 템플릿 안에서 질의 글자에 해당하는 토큰들의 마지막 hidden state [L≤32, 2048]
- pooled: 검색 임베딩과 같은 마지막 토큰(생성 프롬프트 끝) [1, 2048]
Moment-DETR 형식: <out>/<tok|pooled>/qid<qid>.npz, 키 last_hidden_state, float16.

    python ai/experiments/vlm_model/qvh_text_features.py --jsonl <train.jsonl> <train_ko.jsonl> ... --out <dir>
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
QUERY_INSTR = "Retrieve images or video frames relevant to the user's query."
MAX_Q_L = 32


class TextEncoder:
    def __init__(self, embedder=None):
        import speed_opt
        self.e = embedder or speed_opt.Embedder()
        self.p = self.e.proc["torchvision"]; self.tok = self.p.tokenizer

    def _template(self, q):
        msgs = [{"role": "system", "content": [{"type": "text", "text": QUERY_INSTR}]},
                {"role": "user", "content": [{"type": "text", "text": q}]}]
        return self.p.apply_chat_template([msgs], add_generation_prompt=True, tokenize=False)[0]

    @torch.no_grad()
    def encode(self, queries, bs=64):
        """→ [(tok [L,D] float16 np, pooled [1,D] float16 np), ...]"""
        out = []
        for i in range(0, len(queries), bs):
            qs = queries[i:i + bs]
            full = [self._template(q) for q in qs]
            spans = []
            for q, t in zip(qs, full):
                k = t.index(q)
                a = len(self.tok(t[:k], add_special_tokens=False).input_ids)
                b = len(self.tok(t[:k + len(q)], add_special_tokens=False).input_ids)
                spans.append((a, max(b, a + 1)))
            x = self.p(text=full, padding=True, return_tensors="pt").to("cuda")
            h = self.e.m(**x).last_hidden_state.float()
            last = x["attention_mask"].sum(1) - 1
            for j, (a, b) in enumerate(spans):
                out.append((h[j, a:b][:MAX_Q_L].cpu().numpy().astype(np.float16),
                            h[j, last[j]][None].cpu().numpy().astype(np.float16)))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", nargs="+", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); (out / "tok").mkdir(parents=True, exist_ok=True); (out / "pooled").mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for f in a.jsonl for l in open(f)]
    todo = [r for r in rows if not (out / "pooled" / f"qid{r['qid']}.npz").exists()]
    print(f"{time.strftime('%F %T')} 질의 특징: 남은 {len(todo)}개 / 전체 {len(rows)}개", flush=True)
    if not todo:
        return
    enc = TextEncoder()
    for i in range(0, len(todo), 512):
        chunk = todo[i:i + 512]
        for r, (tk, pl) in zip(chunk, enc.encode([r["query"] for r in chunk])):
            np.savez(out / "tok" / f"qid{r['qid']}.npz", last_hidden_state=tk)
            np.savez(out / "pooled" / f"qid{r['qid']}.npz", last_hidden_state=pl)
        print(f"{time.strftime('%F %T')} {min(i + 512, len(todo))}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
