"""SceneFinder 구간 검색 모델(Moment-DETR) CLIP 버전 재현 학습과 VLM 버전 학습, QVH val 평가.

모델 구조·학습 코드(ai/vendor/moment_detr)·학습 옵션은 CLIP 버전(scratch_clip_align, 2026-09-29)과 같고
(seed 2018, 200 epoch, bsz 32, lr 1e-4, contrastive_align_loss 계수 0.02, num_workers 8, ctx_mode video_tef),
특징 폴더와 차원만 바꾼다. 상태 파일(<root>/state/<변형>.json)이 있으면 그 단계는 건너뛴다(이어하기).

변형
- clip_repro: CLIP 영상·텍스트 특징(512), 영어 질의로 학습, 영어 val로 고름
- vlm_<tok|pooled>_enko: Qwen3-VL-Embedding-2B 특징(2048), 영어+한국어 질의로 학습, 한국어 val로 고름
- vlm_<sel>_en / vlm_<sel>_ko: 질의 특징 종류(sel)는 enko 두 개 중 한국어 val MR-full-mAP가 높은 쪽

    python ai/experiments/vlm_model/mr_runs.py prepare|train <변형>|eval_other <변형>|select --root <dir> ...
"""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT_REPO = Path(__file__).resolve().parents[3]
VENDOR = ROOT_REPO / "ai/vendor/moment_detr"
QVH_DATA = Path("/home/team22/jiyeon_experiment/pinpoint-capstone/ai/external/moment_detr/data")
QVH_FEAT = Path("/home/team22/jiyeon_experiment/pinpoint-capstone/ai/external/moment_detr/features")
PY = str(ROOT_REPO / ".venv/bin/python")
COMMON = ["--dset_name", "hl", "--ctx_mode", "video_tef", "--eval_split_name", "val", "--seed", "2018",
          "--num_workers", "8", "--contrastive_align_loss", "--contrastive_align_loss_coef", "0.02"]


def load_jsonl(p):
    return [json.loads(l) for l in open(p)]


def write_jsonl(p, rows):
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def spec(name, a):
    """변형 → (v_feat_dir, t_feat_dir, dim, train jsonl, val jsonl, 다른 언어 val, 다른 언어 t_feat_dir)"""
    d = Path(a.root) / "data"
    if name == "clip_repro":
        return dict(v=str(QVH_FEAT / "clip_features"), t=str(QVH_FEAT / "clip_text_features"), dim=512,
                    train=d / "train_en.jsonl", val=d / "val_en.jsonl", other=None)
    _, kind, lang = name.split("_")
    t = str(Path(a.text_feats) / kind)
    return dict(v=a.vlm_feats, t=t, dim=2048, train=d / f"train_{lang}.jsonl", val=d / "val_ko.jsonl",
                other=d / "val_en.jsonl")


def cmd_prepare(a):
    """영상 특징이 있는 영상의 질의만 남긴 학습·평가 jsonl (CLIP·VLM 모두 같은 질의 집합)."""
    d = Path(a.root) / "data"; d.mkdir(parents=True, exist_ok=True)
    have = {p.stem for p in Path(a.vlm_feats).glob("*.npz")}
    ko = Path(a.text_ko)
    out = {}
    for sp in ("train", "val"):
        en = [r for r in load_jsonl(QVH_DATA / f"highlight_{sp}_release.jsonl") if r["vid"] in have]
        k = [r for r in load_jsonl(ko / f"{sp}_ko.jsonl") if r["vid"] in have]
        assert len(en) == len(k), f"{sp}: 영어 {len(en)} vs 한국어 {len(k)}"
        write_jsonl(d / f"{sp}_en.jsonl", en); write_jsonl(d / f"{sp}_ko.jsonl", k)
        if sp == "train":
            write_jsonl(d / "train_enko.jsonl", en + k)
        total = len(load_jsonl(QVH_DATA / f"highlight_{sp}_release.jsonl"))
        out[sp] = {"queries": len(en), "of_total": total, "videos": len({r['vid'] for r in en})}
    (d / "counts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("데이터:", out)


def state_path(a, name):
    return Path(a.root) / "state" / f"{name}.json"


def run(cmd, cwd, log):
    with open(log, "a") as f:
        f.write(f"\n$ {' '.join(map(str, cmd))}\n"); f.flush()
        p = subprocess.run(list(map(str, cmd)), cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                           env={**os.environ, "PYTHONPATH": str(VENDOR)})
    if p.returncode != 0:
        raise SystemExit(f"실패(exit {p.returncode}): {' '.join(map(str, cmd[:4]))} … 로그 {log}")


def cmd_train(a):
    name = a.name; st = state_path(a, name)
    if st.exists():
        print(f"{name}: 이미 끝남 → 건너뜀"); return
    s = spec(name, a)
    res_root = Path(a.root) / "results"; res_root.mkdir(parents=True, exist_ok=True)
    for old in res_root.glob(f"hl-video_tef-{name}-*"):   # 끝나지 않은 이전 시도는 지우고 처음부터
        shutil.rmtree(old)
    log = Path(a.root) / "logs" / f"train_{name}.log"; log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    run([PY, "moment_detr/train.py", *COMMON, "--exp_id", name, "--results_root", res_root,
         "--train_path", s["train"], "--eval_path", s["val"], "--v_feat_dirs", s["v"], "--t_feat_dir", s["t"],
         "--v_feat_dim", s["dim"], "--t_feat_dim", s["dim"], *(["--n_epoch", a.n_epoch] if a.n_epoch else [])],
        VENDOR, log)
    rd = sorted(res_root.glob(f"hl-video_tef-{name}-*"))[-1]
    m = json.load(open(rd / "best_hl_val_preds_metrics.json"))["brief"]
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"run_dir": str(rd), "val_lang": "en" if name == "clip_repro" else "ko",
                              "val_brief": m, "train_minutes": round((time.time() - t0) / 60, 1)}, ensure_ascii=False, indent=1))
    print(f"{name}: 학습 끝 {m['MR-full-R1@0.5']=}, {m['MR-full-mAP']=}")


def cmd_eval_other(a):
    """VLM 변형을 다른 언어(영어) val로도 평가. 저장된 옵션이 명령줄을 덮어쓰므로 옵션만 바꾼 임시 폴더에서 추론."""
    name = a.name; st = state_path(a, name); s = json.loads(st.read_text())
    if "val_other_brief" in s or name == "clip_repro":
        print(f"{name}: 건너뜀"); return
    sp = spec(name, a); rd = Path(s["run_dir"])
    tmp = Path(a.root) / "eval_other" / name; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    opt = json.load(open(rd / "opt.json")); opt.update(eval_path=str(sp["other"]))
    (tmp / "opt.json").write_text(json.dumps(opt, indent=1))
    os.symlink(rd / "model_best.ckpt", tmp / "model_best.ckpt")
    log = Path(a.root) / "logs" / f"eval_other_{name}.log"
    run([PY, "moment_detr/inference.py", "--resume", tmp / "model_best.ckpt", "--eval_split_name", "val",
         "--eval_path", sp["other"], "--eval_results_dir", tmp, "--eval_id", "other"], VENDOR, log)
    mf = sorted(tmp.glob("*_preds_metrics.json"))
    mf = [p for p in mf if "nms" not in p.name][0]
    s["val_other_lang"] = "en"; s["val_other_brief"] = json.load(open(mf))["brief"]
    st.write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(f"{name}: 영어 val {s['val_other_brief']['MR-full-R1@0.5']=}")


def cmd_select(a):
    """질의 특징 종류 고르기: enko 두 변형 중 한국어 val MR-full-mAP가 높은 쪽 (계획 문서에 결과 전 고정)."""
    sel = Path(a.root) / "state" / "selected_text_feat.json"
    if sel.exists():
        print("이미 고름:", sel.read_text()); return
    m = {k: json.loads(state_path(a, f"vlm_{k}_enko").read_text())["val_brief"]["MR-full-mAP"] for k in ("tok", "pooled")}
    best = max(m, key=m.get)
    sel.write_text(json.dumps({"selected": best, "ko_val_mAP": m}, indent=1)); print("고름:", best, m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("name", nargs="?")
    ap.add_argument("--root", required=True); ap.add_argument("--vlm_feats"); ap.add_argument("--text_feats")
    ap.add_argument("--text_ko"); ap.add_argument("--n_epoch", type=int)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "train": cmd_train, "eval_other": cmd_eval_other, "select": cmd_select}[a.cmd](a)


if __name__ == "__main__":
    main()
