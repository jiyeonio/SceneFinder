"""탐색적(결과 본 뒤 추가, 판정에 쓰지 않음): 구간 검색 VLM 버전을 복지 학습 데이터로 추가 학습(fine-tuning).

- 시작: QVH로 학습한 vlm_tok_ko (복지 dev에서 고른 변형) model_best.ckpt의 가중치
- 데이터: lora_make_data.py의 (질의, 구간) 쌍 (평가 채널이 아닌 학습 영상만). 영상마다 150초(75칸) 창을 정답 구간이
  들어가게 무작위로 잘라(seed 42) QVH와 같은 형식(<vid>.npz features, qid<qid>.npz last_hidden_state)으로 만든다.
  하이라이트 점수는 없어서 정답 칸을 모두 같은 점수(4)로 둔다.
- 학습 영상 중 3개(seed 42)는 체크포인트 고르기용 val로 뺀다(복지 dev는 고르기에 쓰지 않음).
- 학습 코드·옵션은 QVH 학습과 같고(seed 2018 등), lr만 1e-5, epoch 50 (작은 데이터 추가 학습).

    python ai/experiments/vlm_model/mr_finetune.py --root /nfs/team/data/scenefinder_vlm/mr_runs
"""
import argparse, json, math, random, shutil, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import mr_runs

LDATA = Path("/nfs/team/data/scenefinder_vlm/lora_data")
CLIP_LEN, W = 2, 75
NAME = "vlm_tok_ko_ft"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True); ap.add_argument("--base", default="vlm_tok_ko")
    ap.add_argument("--lr", type=float, default=1e-5); ap.add_argument("--n_epoch", type=int, default=50)
    ap.add_argument("--n_val_videos", type=int, default=3)
    a = ap.parse_args()
    root = Path(a.root); ft = root / "ft"
    st = root / "state_ft" / f"{NAME}.json"
    if st.exists():
        print("이미 끝남", st.read_text()); return
    rng = random.Random(42)
    pairs = [json.loads(l) for l in open(LDATA / "pairs.jsonl")]
    vids = sorted({p["vid"] for p in pairs}); val_vids = set(rng.sample(vids, a.n_val_videos))
    (ft / "vfeat").mkdir(parents=True, exist_ok=True); (ft / "tfeat").mkdir(exist_ok=True)
    feats = {v: torch.load(LDATA / "qwen_640" / f"{v}.pt").float().numpy() for v in vids}
    from qvh_text_features import TextEncoder
    enc = TextEncoder()
    rows = {"train": [], "val": []}
    for qi, p in enumerate(pairs):
        f = feats[p["vid"]]; n = len(f)
        b0, b1 = int(p["start"] // CLIP_LEN), min(n, int(math.ceil(p["end"] / CLIP_LEN)))
        w = min(W, n)
        if b1 - b0 > w or b1 <= b0:
            continue
        ws = rng.randint(max(0, b1 - w), min(b0, n - w))
        wid = f"{p['vid']}_{ws:04d}"
        if not (ft / "vfeat" / f"{wid}.npz").exists():
            np.savez(ft / "vfeat" / f"{wid}.npz", features=f[ws:ws + w].astype(np.float32))
        qid = 2_000_000 + qi
        tok, _ = enc.encode([p["query"]])[0]
        np.savez(ft / "tfeat" / f"qid{qid}.npz", last_hidden_state=tok.astype(np.float32))
        s, e = max(0.0, p["start"] - ws * CLIP_LEN), min(w * CLIP_LEN, p["end"] - ws * CLIP_LEN)
        clip_ids = list(range(int(s // CLIP_LEN), min(w, int(math.ceil(e / CLIP_LEN)))))
        rows["val" if p["vid"] in val_vids else "train"].append({
            "qid": qid, "query": p["query"], "duration": w * CLIP_LEN, "vid": wid, "relevant_windows": [[round(s, 2), round(e, 2)]],
            "relevant_clip_ids": clip_ids, "saliency_scores": [[4, 4, 4]] * len(clip_ids), "kind": p["kind"]})
    del enc; torch.cuda.empty_cache()
    for sp, rs in rows.items():
        mr_runs.write_jsonl(ft / f"{sp}.jsonl", rs)
    print(f"추가 학습 데이터: train {len(rows['train'])}, val {len(rows['val'])} (val 영상 {sorted(val_vids)})", flush=True)

    base = json.loads((root / "state" / f"{a.base}.json").read_text())
    res = ft / "results"; res.mkdir(exist_ok=True)
    for old in res.glob(f"hl-video_tef-{NAME}-*"):
        shutil.rmtree(old)
    log = root / "logs" / f"train_{NAME}.log"
    t0 = time.time()
    mr_runs.run([mr_runs.PY, "moment_detr/train.py", *mr_runs.COMMON, "--exp_id", NAME, "--results_root", res,
                 "--train_path", ft / "train.jsonl", "--eval_path", ft / "val.jsonl", "--v_feat_dirs", ft / "vfeat",
                 "--t_feat_dir", ft / "tfeat", "--v_feat_dim", 2048, "--t_feat_dim", 2048,
                 "--resume", Path(base["run_dir"]) / "model_best.ckpt", "--lr", a.lr, "--n_epoch", a.n_epoch], mr_runs.VENDOR, log)
    rd = sorted(res.glob(f"hl-video_tef-{NAME}-*"))[-1]
    m = json.load(open(rd / "best_hl_val_preds_metrics.json"))["brief"]
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"run_dir": str(rd), "ckpt": str(rd / "model_best.ckpt"), "base": a.base, "lr": a.lr, "n_epoch": a.n_epoch,
                              "n_train": len(rows["train"]), "n_val": len(rows["val"]), "val_videos": sorted(val_vids),
                              "welfare_val_brief": m, "train_minutes": round((time.time() - t0) / 60, 1)}, ensure_ascii=False, indent=1))
    print(f"{NAME}: 복지 val {m['MR-full-R1@0.5']=} {m['MR-full-mAP']=}")


if __name__ == "__main__":
    main()
