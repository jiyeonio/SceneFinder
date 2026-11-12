"""QVHighlights 질의 영→한 번역 (로컬 Qwen3-VL-4B-Instruct, greedy). train·val만 (test는 정답이 공개되지 않아 쓰지 않음).

출력: <out>/<split>_ko.jsonl — 원본 줄을 그대로 두고 qid를 KO_QID_OFFSET만큼 옮기고 query를 한국어로 바꾼 것,
      <out>/translations.jsonl — {qid, split, en, ko} (이어하기용, 한 줄씩 바로 씀)

    python ai/experiments/vlm_model/qvh_translate.py --out /nfs/team/data/scenefinder_vlm/qvh/text_ko
"""
import argparse, json, time
from pathlib import Path

import torch

QVH_DATA = Path("/home/team22/jiyeon_experiment/pinpoint-capstone/ai/external/moment_detr/data")
KO_QID_OFFSET = 1_000_000
MODEL = "Qwen/Qwen3-VL-4B-Instruct"
PROMPT = ("다음 영어 문장은 영상에서 장면을 찾는 검색어입니다. 자연스러운 한국어 검색 문장으로 번역하세요. "
          "뜻을 바꾸거나 설명을 덧붙이지 말고 번역문만 한 줄로 쓰세요.\n\n{en}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--splits", default="train,val")
    ap.add_argument("--limit_vids", help="이 영상들의 질의만 (시험용, 줄마다 vid 하나)")
    ap.add_argument("--bs", type=int, default=64)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    keep = set(Path(a.limit_vids).read_text().split()) if a.limit_vids else None
    rows = {sp: [json.loads(l) for l in open(QVH_DATA / f"highlight_{sp}_release.jsonl")] for sp in a.splits.split(",")}
    if keep is not None:
        rows = {sp: [r for r in rs if r["vid"] in keep] for sp, rs in rows.items()}
    tpath = out / "translations.jsonl"
    done = {json.loads(l)["qid"]: json.loads(l)["ko"] for l in open(tpath)} if tpath.exists() else {}
    todo = [(sp, r) for sp, rs in rows.items() for r in rs if r["qid"] not in done]
    print(f"{time.strftime('%F %T')} 번역 시작: 남은 질의 {len(todo)}개 (이미 {len(done)}개)", flush=True)
    if todo:
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        proc = AutoProcessor.from_pretrained(MODEL); proc.tokenizer.padding_side = "left"
        model = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16).cuda().eval()
        f = open(tpath, "a")
        t0 = time.time()
        for i in range(0, len(todo), a.bs):
            chunk = todo[i:i + a.bs]
            msgs = [[{"role": "user", "content": [{"type": "text", "text": PROMPT.format(en=r["query"])}]}] for _, r in chunk]
            text = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
            x = proc(text=text, padding=True, return_tensors="pt").to("cuda")
            with torch.no_grad():
                y = model.generate(**x, max_new_tokens=64, do_sample=False)
            outs = proc.batch_decode(y[:, x["input_ids"].shape[1]:], skip_special_tokens=True)
            for (sp, r), ko in zip(chunk, outs):
                ko = ko.strip().splitlines()[0].strip().strip('"') if ko.strip() else ""
                done[r["qid"]] = ko
                f.write(json.dumps({"qid": r["qid"], "split": sp, "en": r["query"], "ko": ko}, ensure_ascii=False) + "\n")
            f.flush()
            if (i // a.bs) % 20 == 0:
                print(f"{time.strftime('%F %T')} {min(i + a.bs, len(todo))}/{len(todo)} ({time.time() - t0:.0f}초)", flush=True)
    empty = sum(1 for v in done.values() if not v)
    for sp, rs in rows.items():
        with open(out / f"{sp}_ko.jsonl", "w") as g:
            for r in rs:
                g.write(json.dumps({**r, "qid": r["qid"] + KO_QID_OFFSET, "query": done[r["qid"]], "query_en": r["query"]},
                                   ensure_ascii=False) + "\n")
    print(f"{time.strftime('%F %T')} 번역 끝: {len(done)}개 (빈 번역 {empty}개)", flush=True)
    if empty:
        raise SystemExit(f"빈 번역 {empty}개")


if __name__ == "__main__":
    main()
