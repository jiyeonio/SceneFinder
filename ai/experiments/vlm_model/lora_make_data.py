"""화면 검색 LoRA·구간 검색 추가 학습용 복지 학습 데이터 만들기 (평가 채널이 아닌 학습 영상만).

단계 (각각 이어하기 가능, GPU는 한 단계씩):
  prep   : 영상마다 자막(서비스와 같은 Whisper large-v3-turbo), 2초 칸 가운데 프레임(640×360, 평가와 같은 디코딩)
           → <out>/frames/<vid>.npy, Qwen3-VL-Embedding-2B 특징 → <out>/qwen_640/<vid>.pt, 자막 → <out>/subs/<vid>.json
  gen    : 로컬 Qwen3-VL-4B-Instruct(greedy)로 질의 생성
           (b-1) 화면 글자 기반 질의, (b-2) 사용자 말투 질문(사용자 유형을 돌려 가며, 약 1/4은 애매하게),
           (b-3) 제목 먼저: 제목·정책만 보고 질문을 쓰고 → 같은 모델이 구간 목록(자막·화면 설명)에서 답 구간을 찾음, 없으면 버림
  filter : 평가 질의(dev·test AI 초안·사용자 질문 전부)와 글자 3-gram 자카드 ≥ 0.8인 질의 제거, 평가 영상 ID 검사
           → <out>/pairs.jsonl 와 저장소 labels/lora_train_pairs.jsonl

구간: 자막 문장을 이어 붙여 10~16초 덩어리(자막이 없으면 12초씩). 정답 = 그 덩어리 [start, end].
프롬프트의 예시 문장은 복지와 무관한 주제로 새로 썼고, 평가 질의를 예시로 쓰지 않는다.

    python ai/experiments/vlm_model/lora_make_data.py prep|gen|filter --out /nfs/team/data/scenefinder_vlm/lora_data
"""
import argparse, csv, json, math, os, re, sys, time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services"), str(HERE)]
os.environ.setdefault("WHISPER_MODEL_SIZE", "large-v3-turbo")
VIDEOS = Path("/nfs/team/data/scenefinder_vlm/lora_videos")
TRAIN_TSV = ROOT / "docs/experiments/vlm_lora_train_videos.tsv"
CLIP_LEN = 2
GEN_MODEL = "Qwen/Qwen3-VL-4B-Instruct"
PERSONAS = ["혼자 사는 70대 어르신", "취업 준비 중인 20대 청년", "어린아이를 키우는 부모", "부모님 대신 알아보는 자녀",
            "장애가 있는 가족을 돌보는 사람", "형편이 갑자기 어려워진 40대 직장인"]
SEED = 42


def train_rows():
    rows = list(csv.DictReader(open(TRAIN_TSV), delimiter="\t"))
    split = list(csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_split.tsv"), delimiter="\t"))
    excl = {r["youtube_id"] for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_train_exclude.tsv"), delimiter="\t")}
    bad = {r["youtube_id"] for r in rows} & ({r["youtube_id"] for r in split} | excl)
    bad_ch = {r["channel_id"] for r in rows} & {r["channel_id"] for r in split}
    assert not bad and not bad_ch, f"평가 영상/채널이 학습 목록에 있음: {bad} {bad_ch}"
    return [r for r in rows if (VIDEOS / f"{r['youtube_id']}.mp4").exists()]


# ---------------------------------------------------------------- prep
def prep(out):
    rows = train_rows()
    (out / "subs").mkdir(parents=True, exist_ok=True); (out / "frames").mkdir(exist_ok=True); (out / "qwen_640").mkdir(exist_ok=True)
    todo = [r for r in rows if not (out / "subs" / f"{r['youtube_id']}.json").exists()]
    if todo:
        from subtitles import _transcribe, MIN_SUBTITLE_SEGMENTS, MIN_SUBTITLE_CHARS
        for r in todo:
            vid = r["youtube_id"]; t0 = time.time()
            items, lang, prob = _transcribe(str(VIDEOS / f"{vid}.mp4"))
            if len(items) < MIN_SUBTITLE_SEGMENTS or sum(len(i["text"]) for i in items) < MIN_SUBTITLE_CHARS:
                items = []
            (out / "subs" / f"{vid}.json").write_text(json.dumps({"source": "whisper_large-v3-turbo", "language": lang,
                                                                   "segments": items}, ensure_ascii=False, indent=1))
            print(f"자막 {vid} 문장 {len(items)} ({time.time() - t0:.0f}초)", flush=True)
        import gc; del _transcribe; gc.collect(); torch.cuda.empty_cache()
    import speed_opt
    emb = None
    for r in rows:
        vid = r["youtube_id"]
        if (out / "qwen_640" / f"{vid}.pt").exists():
            continue
        if emb is None:
            emb = speed_opt.Embedder()
        dur = float(r["duration_sec"]); n = math.ceil(dur / CLIP_LEN)
        frames = speed_opt.decode(VIDEOS / f"{vid}.mp4", n, "cpu")
        np.save(out / "frames" / f"{vid}.npy", frames)
        e, _, _ = emb(frames, "torchvision", "cuda", 16)
        torch.save(e.half().cpu(), out / "qwen_640" / f"{vid}.pt")
        print(f"특징 {vid} 칸 {n}", flush=True)


def chunks_of(subs, dur):
    """자막 문장을 이어 10~16초 덩어리. 자막이 없거나 빈 곳이 길면 12초씩."""
    segs = [(float(s["start_time"]), float(s["end_time"]), s["text"].strip()) for s in subs if s["text"].strip()]
    out, cur = [], None
    for s, e, t in segs:
        if cur and (s - cur[1] > 4 or e - cur[0] > 16):
            out.append(cur); cur = None
        cur = [s, e, t] if cur is None else [cur[0], e, cur[2] + " " + t]
        if cur[1] - cur[0] >= 10:
            out.append(cur); cur = None
    if cur:
        out.append(cur)
    out = [c for c in out if c[1] - c[0] >= 4]
    if not out:
        out = [[s, min(dur, s + 12), ""] for s in np.arange(0, max(dur - 4, 1), 12).tolist()]
    return [{"start": round(c[0], 2), "end": round(min(c[1], dur), 2), "text": c[2]} for c in out]


# ---------------------------------------------------------------- gen
CHUNK_PROMPT = """복지·행정 안내 영상의 한 장면입니다. 이미지 2장은 이 장면의 앞부분과 뒷부분이고, 아래는 이 장면의 자막입니다.
자막: {text}

이 장면을 찾게 해 주는 검색 질의를 만들려고 합니다. 아래 JSON 하나만 쓰세요.
{{"screen_text": "화면에 보이는 주요 글자(제목·버튼·칸 이름 등, 없으면 빈 문자열)",
 "screen_desc": "화면이 어떤 모습인지 한 문장",
 "q_screen": "화면 글자를 넣어 이 장면을 찾는 짧은 검색 질의 (화면에 글자가 없으면 null)",
 "q_user": ["{p1}의 말투로 쓴 질문", "{p2}의 말투로 쓴 질문"]}}

q_user 규칙: 이 장면이 답이 되는 질문을, 그 사람이 스마트폰에 직접 입력하듯 짧고 일상적인 말투로 씁니다.
행정용어나 화면 글자를 그대로 베끼지 말고 쉬운 말로 바꿉니다.{vague}
말투 예시(주제는 무관): "도서관 책 반납 기한 늘리는 거 어디서 눌러?", "애 학교 급식표 핸드폰으로 보는 법"
"""
VAGUE = " 두 번째 질문은 무엇을 원하는지 조금 애매하게 씁니다(예: \"그거 신청 어떻게 해\")."
TITLE_PROMPT = """아래는 유튜브 복지·행정 안내 영상의 제목과 다루는 정책입니다. 영상 내용은 보지 않았습니다.
제목: {title}
정책: {policy}

이 영상을 찾아볼 법한 사람이 궁금해할 질문 6개를 쓰세요. 사용자 유형을 섞습니다: {personas}.
스마트폰에 직접 입력하듯 짧고 일상적인 말투, 행정용어는 쉬운 말로. 그중 1~2개는 조금 애매하게.
JSON 배열 하나만 쓰세요: ["질문1", ..., "질문6"]"""
FIND_PROMPT = """복지 안내 영상을 장면별로 나눈 목록입니다(번호, 시간, 자막, 화면 설명).
{listing}

질문: {q}
이 질문에 직접 도움이 되는 정보가 나오는 장면 번호 하나를 고르세요. 비슷한 주제일 뿐 답이 없으면 -1.
숫자 하나만 쓰세요."""


def parse_json(s, kind):
    s = s.strip().strip("`")
    s = re.sub(r"^json\s*", "", s)
    m = re.search(r"\{.*\}" if kind == "obj" else r"\[.*\]", s, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


class Gen:
    def __init__(self):
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.proc = AutoProcessor.from_pretrained(GEN_MODEL); self.proc.tokenizer.padding_side = "left"
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(GEN_MODEL, dtype=torch.bfloat16).cuda().eval()

    @torch.no_grad()
    def __call__(self, msgs, max_new=256):
        from PIL import Image
        text = self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        imgs = [Image.fromarray(c["image"]) for m in msgs for c in m[0]["content"] if c["type"] == "image"]
        x = self.proc(text=text, images=imgs or None, padding=True, return_tensors="pt").to("cuda")
        y = self.model.generate(**x, max_new_tokens=max_new, do_sample=False)
        return [o.strip() for o in self.proc.batch_decode(y[:, x["input_ids"].shape[1]:], skip_special_tokens=True)]


def gen(out, bs):
    rows = [r for r in train_rows() if (out / "qwen_640" / f"{r['youtube_id']}.pt").exists()]   # prep 끝난 영상만
    g = Gen()
    cpath = out / "chunks.jsonl"
    done = {json.loads(l)["cid"] for l in open(cpath)} if cpath.exists() else set()
    f = open(cpath, "a")
    ci = 0
    for r in rows:
        vid = r["youtube_id"]
        subs = json.loads((out / "subs" / f"{vid}.json").read_text())["segments"]
        frames = np.load(out / "frames" / f"{vid}.npy")
        chs = chunks_of(subs, float(r["duration_sec"]))
        todo = []
        for k, c in enumerate(chs):
            cid = f"{vid}_{k:03d}"; ci += 1
            if cid in done:
                continue
            b1 = min(len(frames) - 1, int((c["start"] + (c["end"] - c["start"]) / 3) // CLIP_LEN))
            b2 = min(len(frames) - 1, int((c["start"] + 2 * (c["end"] - c["start"]) / 3) // CLIP_LEN))
            p1, p2 = PERSONAS[(2 * ci) % len(PERSONAS)], PERSONAS[(2 * ci + 1) % len(PERSONAS)]
            vague = ci % 2 == 0   # 두 번째 질문을 애매하게 → 사용자 질문의 약 1/4
            todo.append((cid, k, c, [b1, b2], p1, p2, vague))
        t0 = time.time()
        for i in range(0, len(todo), bs):
            part = todo[i:i + bs]
            msgs = [[{"role": "user", "content": [{"type": "image", "image": frames[b]} for b in bins] +
                      [{"type": "text", "text": CHUNK_PROMPT.format(text=c["text"] or "(자막 없음)", p1=p1, p2=p2, vague=VAGUE if vague else "")}]}]
                    for _, _, c, bins, p1, p2, vague in part]
            for (cid, k, c, bins, p1, p2, vague), o in zip(part, g(msgs)):
                j = parse_json(o, "obj") or {}
                f.write(json.dumps({"cid": cid, "vid": vid, "k": k, **c, "bins": bins, "personas": [p1, p2], "vague2": vague,
                                    "out": j, "raw": None if j else o}, ensure_ascii=False) + "\n")
            f.flush()
        print(f"장면 질의 {vid}: 장면 {len(chs)}개, 새로 {len(todo)}개 ({time.time() - t0:.0f}초)", flush=True)

    # (b-3) 제목 먼저
    tpath = out / "title_first.jsonl"
    tdone = {json.loads(l)["vid"] for l in open(tpath)} if tpath.exists() else set()
    tf = open(tpath, "a")
    allch = {}
    for l in open(cpath):
        c = json.loads(l); allch.setdefault(c["vid"], []).append(c)
    for vi, r in enumerate(rows):
        vid = r["youtube_id"]
        if vid in tdone:
            continue
        ps = ", ".join(PERSONAS[(vi + j) % len(PERSONAS)] for j in range(4))
        qs = parse_json(g([[{"role": "user", "content": [{"type": "text", "text": TITLE_PROMPT.format(
            title=r["title"], policy=r["policy"], personas=ps)}]}]])[0], "arr") or []
        chs = sorted(allch.get(vid, []), key=lambda c: c["k"])
        listing = "\n".join(f"[{c['k']}] {int(c['start']) // 60}:{int(c['start']) % 60:02d}~{int(c['end']) // 60}:{int(c['end']) % 60:02d} "
                            f"자막: {c['text'][:120] or '(없음)'} / 화면: {(c['out'] or {}).get('screen_desc', '')} "
                            f"{(c['out'] or {}).get('screen_text', '')}"[:300] for c in chs)
        res = []
        qs = [q for q in qs if isinstance(q, str) and q.strip()][:6]
        for i in range(0, len(qs), bs):
            outs = g([[{"role": "user", "content": [{"type": "text", "text": FIND_PROMPT.format(listing=listing, q=q)}]}]
                      for q in qs[i:i + bs]], max_new=8)
            for q, o in zip(qs[i:i + bs], outs):
                m = re.search(r"-?\d+", o); k = int(m.group(0)) if m else -1
                hit = next((c for c in chs if c["k"] == k), None)
                res.append({"query": q.strip(), "k": k if hit else -1, "start": hit["start"] if hit else None,
                            "end": hit["end"] if hit else None})
        tf.write(json.dumps({"vid": vid, "title": r["title"], "personas": ps, "results": res}, ensure_ascii=False) + "\n"); tf.flush()
        print(f"제목 먼저 {vid}: 질문 {len(qs)}개, 답 구간 찾음 {sum(x['k'] >= 0 for x in res)}개", flush=True)


# ---------------------------------------------------------------- filter
def grams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 3] for i in range(max(1, len(s) - 2))}


def jacc(a, b):
    return len(a & b) / max(1, len(a | b))


def filt(out):
    rows = train_rows(); vids = {r["youtube_id"] for r in rows}
    seen = set()
    labels = json.loads((HERE / "labels/review.json").read_text())
    sim = json.loads((ROOT / "docs/experiments/vlm_eval_sim_queries.json").read_text())
    ev = [q["query"] for q in labels["queries"] + labels.get("negative_queries", [])] + \
         [q["query"] for qs in sim["queries"].values() for q in qs]
    evg = [grams(q) for q in ev]
    ev_ids = {v["youtube_id"] for v in labels["videos"].values()}
    assert not (vids & ev_ids), "평가 영상이 학습 데이터에 있음"
    pairs, drop = [], {"parse": 0, "leak": 0, "copy_screen": 0, "empty": 0, "dup": 0}

    def add(vid, kind, q, s, e, bins, **kw):
        if not isinstance(q, str) or len(q.strip()) < 4:
            drop["empty"] += 1; return
        q = q.strip().strip('"')
        if (vid, q) in seen:   # 같은 영상 안 같은 질의(두 사용자 질문이 똑같이 나온 경우 등)
            drop["dup"] += 1; return
        seen.add((vid, q))
        g = grams(q)
        if max(jacc(g, x) for x in evg) >= 0.8:
            drop["leak"] += 1; return
        pairs.append({"vid": vid, "kind": kind, "query": q, "start": s, "end": e, "bins": bins, **kw})

    for l in open(out / "chunks.jsonl"):
        c = json.loads(l); j = c["out"]
        if not j:
            drop["parse"] += 1; continue
        st = j.get("screen_text") or ""
        if j.get("q_screen") and st:
            add(c["vid"], "b1_screen", j["q_screen"], c["start"], c["end"], c["bins"])
        for i, q in enumerate((j.get("q_user") or [])[:2]):
            # 화면 글자를 그대로 베낀 사용자 질문은 뺌 (계획: 화면 글자를 그대로 쓰지 않음)
            if isinstance(q, str) and st and len(grams(q) & grams(st)) / max(1, len(grams(q))) > 0.6:
                drop["copy_screen"] += 1; continue
            add(c["vid"], "b2_user", q, c["start"], c["end"], c["bins"], persona=c["personas"][i], vague=bool(i == 1 and c["vague2"]))
    for l in (open(out / "title_first.jsonl") if (out / "title_first.jsonl").exists() else []):
        t = json.loads(l)
        for x in t["results"]:
            if x["k"] >= 0:
                b = [int((x["start"] + (x["end"] - x["start"]) / 3) // CLIP_LEN), int((x["start"] + 2 * (x["end"] - x["start"]) / 3) // CLIP_LEN)]
                add(t["vid"], "b3_title_first", x["query"], x["start"], x["end"], b)
    with open(out / "pairs.jsonl", "w") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (HERE / "labels/lora_train_pairs.jsonl").write_text((out / "pairs.jsonl").read_text())
    from collections import Counter
    stats = {"pairs": len(pairs), "by_kind": Counter(p["kind"] for p in pairs), "dropped": drop,
             "videos": len({p["vid"] for p in pairs}), "vague_user": sum(p.get("vague", False) for p in pairs)}
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "gen", "filter"])
    ap.add_argument("--out", default="/nfs/team/data/scenefinder_vlm/lora_data")
    ap.add_argument("--bs", type=int, default=8)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(SEED)
    {"prep": lambda: prep(out), "gen": lambda: gen(out, a.bs), "filter": lambda: filt(out)}[a.cmd]()


if __name__ == "__main__":
    main()
