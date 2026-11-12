"""화면 검색 Qwen3-VL-Embedding-2B LoRA 학습 (vlm_model_plan.md 「화면 검색 LoRA」 설정 그대로).

학습 쌍 (한국어 질의, 프레임):
  - welfare: lora_make_data.py가 만든 복지 학습 영상 질의(b-1·b-2·b-3). 양성 = 정답 구간 안 칸, 어려운 오답 = 같은 영상의 20초 넘게 떨어진 칸
  - qvh: QVHighlights train 한국어 번역 질의 중 --n_qvh개(seed 42). 양성 = 정답 구간 안 칸, 어려운 오답 = 같은 영상 정답 밖 칸
변형: mix(welfare + qvh) / welfare(복지만). 손실: InfoNCE(질의 vs 묶음 안 모든 양성·어려운 오답), 온도 0.05.
LoRA r16·α32·dropout 0.05, q·k·v·o, lr 1e-4, epoch 2(epoch마다 저장), 묶음 16, seed 42.
epoch마다 **dev** 영상 프레임 특징을 LoRA 모델로 다시 뽑아 둔다(test 영상은 다루지 않음) → prelim_eval.py --lora로 평가.

    python ai/experiments/vlm_model/lora_train.py --variant mix --out /nfs/team/data/scenefinder_vlm/lora_runs
"""
import argparse, csv, json, math, random, subprocess, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path[:0] = [str(ROOT), str(HERE)]
DATA = Path("/nfs/team/data/scenefinder_vlm")
LDATA = DATA / "lora_data"
QVH_VIDEOS = DATA / "qvh/videos/videos"
QVH_KO = DATA / "qvh/text_ko/train_ko.jsonl"
CLIP_LEN = 2
DOC_INSTR = "Represent the user's input."
Q_INSTR = "Retrieve images or video frames relevant to the user's query."


def welfare_items(rng):
    items = []
    for l in open(LDATA / "pairs.jsonl"):
        p = json.loads(l)
        n = len(np.load(LDATA / "frames" / f"{p['vid']}.npy", mmap_mode="r"))
        b0, b1 = int(p["start"] // CLIP_LEN), min(n - 1, int(math.ceil(p["end"] / CLIP_LEN)) - 1)
        far = [i for i in range(n) if i < b0 - 10 or i > b1 + 10]
        if b1 < b0 or not far:
            continue
        items.append({"src": "welfare", "query": p["query"], "vid": p["vid"], "pos": list(range(b0, b1 + 1)), "neg": far})
    return items


def qvh_items(rng, n_qvh, cache):
    rows = [json.loads(l) for l in open(QVH_KO)]
    rows = [r for r in rows if (QVH_VIDEOS / f"{r['vid']}.mp4").exists() and r["query"].strip()]
    rng.shuffle(rows)
    cache.mkdir(parents=True, exist_ok=True)
    import speed_opt
    items = []
    for r in rows[:n_qvh]:
        f = cache / f"{r['qid']}.npy"
        n = int(r["duration"] // CLIP_LEN)
        inside = sorted({i for s, e in r["relevant_windows"] for i in range(int(s // CLIP_LEN), min(n, int(math.ceil(e / CLIP_LEN))))})
        outside = [i for i in range(n) if all(i < s // CLIP_LEN - 2 or i >= math.ceil(e / CLIP_LEN) + 2 for s, e in r["relevant_windows"])]
        if not inside or not outside:
            continue
        pb, nb = rng.choice(inside), rng.choice(outside)
        if not f.exists():
            fr = speed_opt.decode(QVH_VIDEOS / f"{r['vid']}.mp4", n, "cpu")
            np.save(f, np.stack([fr[min(pb, len(fr) - 1)], fr[min(nb, len(fr) - 1)]]))
        items.append({"src": "qvh", "query": r["query"], "qid": r["qid"], "file": str(f)})
    return items


def frames_of(it, rng, cache_np):
    if it["src"] == "qvh":
        a = np.load(it["file"]); return a[0], a[1]
    if it["vid"] not in cache_np:
        cache_np[it["vid"]] = np.load(LDATA / "frames" / f"{it['vid']}.npy", mmap_mode="r")
    fr = cache_np[it["vid"]]
    return np.asarray(fr[rng.choice(it["pos"])]), np.asarray(fr[rng.choice(it["neg"])])


def embed(model, proc, texts=None, images=None, instr=None):
    if images is not None:
        msgs = [{"role": "system", "content": [{"type": "text", "text": DOC_INSTR}]}, {"role": "user", "content": [{"type": "image"}]}]
        t = proc.apply_chat_template([msgs], add_generation_prompt=True, tokenize=False)[0]
        ims = torch.from_numpy(np.ascontiguousarray(np.stack(images))).permute(0, 3, 1, 2).cuda()
        x = proc(text=[t] * len(ims), images=list(ims), padding=True, return_tensors="pt", device="cuda").to("cuda")
    else:
        msgs = [[{"role": "system", "content": [{"type": "text", "text": Q_INSTR}]}, {"role": "user", "content": [{"type": "text", "text": q}]}]
                for q in texts]
        x = proc(text=proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False), padding=True, return_tensors="pt").to("cuda")
    h = model(**x).last_hidden_state
    last = x["attention_mask"].sum(1) - 1
    return F.normalize(h[torch.arange(h.shape[0], device=h.device), last].float(), dim=-1)


def dev_features(emb, out_dir):
    """dev 영상만. 칸 수는 평가 특징(eval_features/clip)과 맞춤."""
    import speed_opt
    rows = [r for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_split.tsv"), delimiter="\t") if r["split"] == "dev"]
    assert rows and all(r["split"] == "dev" for r in rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        n = len(torch.load(DATA / "eval_features/clip" / f"{r['youtube_id']}_clip_features.pt"))
        frames = speed_opt.decode(DATA / "eval_videos" / f"{r['youtube_id']}.mp4", n, "cpu")
        e, _, _ = emb(frames, "torchvision", "cuda", 16)
        torch.save(e.half().cpu(), out_dir / f"{r['youtube_id']}.pt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["mix", "welfare"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n_qvh", type=int, default=2000)
    ap.add_argument("--epochs", type=int, default=2); ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--tau", type=float, default=0.05)
    ap.add_argument("--r", type=int, default=16); ap.add_argument("--alpha", type=int, default=32); ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42); ap.add_argument("--max_steps", type=int, default=0, help="시험용")
    a = ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    rng = random.Random(a.seed)
    run = Path(a.out) / a.variant; run.mkdir(parents=True, exist_ok=True)
    if (run / f"ep{a.epochs}" / "DONE").exists():
        print("이미 끝남", run); return

    items = welfare_items(rng)
    nw = len(items)
    if a.variant == "mix":
        items += qvh_items(rng, a.n_qvh, LDATA / "qvh_frames")
    print(f"학습 쌍: 복지 {nw}, QVH {len(items) - nw}", flush=True)

    import speed_opt
    from lora import apply_lora, lora_state
    emb = speed_opt.Embedder()
    model, proc = emb.m, emb.proc["torchvision"]
    names = apply_lora(model, a.r, a.alpha, a.dropout)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    print(f"LoRA 층 {len(names)}개, 학습 변수 {sum(p.numel() for p in params) / 1e6:.2f}M", flush=True)
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
    steps_ep = len(items) // a.bs
    total = a.max_steps or steps_ep * a.epochs
    warm = max(1, int(0.05 * total))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""
    cfg = {**vars(a), "n_welfare": nw, "n_qvh_used": len(items) - nw, "steps_per_epoch": steps_ep, "commit": commit,
           "loss": "InfoNCE q vs [pos; hard neg] in batch", "targets": "language_model self_attn q,k,v,o"}
    (run / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    log = open(run / "train_log.jsonl", "a")
    cache_np, step, t0 = {}, 0, time.time()
    for ep in range(1, a.epochs + 1):
        order = list(range(len(items))); rng.shuffle(order)
        for i in range(0, steps_ep * a.bs, a.bs):
            batch = [items[j] for j in order[i:i + a.bs]]
            pf = [frames_of(it, rng, cache_np) for it in batch]
            with torch.autocast("cuda", dtype=torch.bfloat16):
                qv = embed(model, proc, texts=[it["query"] for it in batch])
                iv = embed(model, proc, images=[p for p, _ in pf] + [n for _, n in pf])
            logits = qv @ iv.t() / a.tau
            loss = F.cross_entropy(logits, torch.arange(len(batch), device="cuda"))
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step(); step += 1
            acc = (logits.argmax(1) == torch.arange(len(batch), device="cuda")).float().mean().item()
            if step % 10 == 0 or step == 1:
                rec = {"ep": ep, "step": step, "loss": round(loss.item(), 4), "acc": round(acc, 3), "lr": sched.get_last_lr()[0],
                       "sec": round(time.time() - t0), "gpu_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
                log.write(json.dumps(rec) + "\n"); log.flush(); print(rec, flush=True)
            if a.max_steps and step >= a.max_steps:
                break
        d = run / f"ep{ep}"; d.mkdir(exist_ok=True)
        torch.save(lora_state(model), d / "adapter.pt")
        model.eval()
        with torch.no_grad():
            dev_features(emb, d / "dev_qwen_640")
        model.train()
        (d / "DONE").write_text(f"{time.strftime('%F %T')} {round((time.time() - t0) / 60, 1)}분\n")
        print(f"epoch {ep} 저장 → {d}", flush=True)
        if a.max_steps and step >= a.max_steps:
            break


if __name__ == "__main__":
    main()
