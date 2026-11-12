"""구간 검색 모델 CLIP 버전(재현) vs VLM 버전 결과 문서 초안을 자동으로 만든다 (사람 확인 전, 커밋 전).

    python ai/experiments/vlm_model/mr_report.py --root <mr_runs 폴더> --dev <dev 평가 폴더> --out docs/experiments/vlm_mr_results_draft.md
"""
import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True); ap.add_argument("--dev", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--text_ko", default="/nfs/team/data/scenefinder_vlm/qvh/text_ko")
    a = ap.parse_args()
    root = Path(a.root)
    st = {p.stem: json.loads(p.read_text()) for p in sorted((root / "state").glob("*.json")) if p.stem != "selected_text_feat"}
    sel = json.loads((root / "state/selected_text_feat.json").read_text()) if (root / "state/selected_text_feat.json").exists() else {}
    counts = json.loads((root / "data/counts.json").read_text())
    tables = Path(a.dev) / "tables.md"
    subprocess.run([sys.executable, str(ROOT / "ai/experiments/vlm_model/prelim_report.py"), "--res", a.dev, "--out", str(tables)], check=True)
    rows = json.loads((Path(a.dev) / "rows.json").read_text())

    def r1(name, f=lambda r: True):
        sub = [r for r in rows if f(r) and name in r]
        return f"{sum(r[name]['iou'] >= 0.3 for r in sub) / len(sub) * 100:.0f}% ({sum(r[name]['iou'] >= 0.3 for r in sub)}/{len(sub)})" if sub else "–"

    L = [f"# 구간 검색 모델 CLIP 버전 vs VLM 버전 — 결과 초안 (자동 생성 {datetime.now():%Y-%m-%d %H:%M}, 사람 확인·커밋 전)", "",
         "> 자동 파이프라인(qvh_next.sh)이 만든 초안입니다. 숫자는 스크립트가 그대로 옮긴 것이고, 해석은 사람이 확인한 뒤 씁니다. **test는 돌리지 않았습니다.**", "",
         "## 학습 데이터", "",
         f"- QVHighlights 특징이 있는 영상의 질의만: train {counts['train']['queries']}/{counts['train']['of_total']}개 질의({counts['train']['videos']}개 영상), "
         f"val {counts['val']['queries']}/{counts['val']['of_total']}개({counts['val']['videos']}개 영상). CLIP·VLM 모두 같은 질의 집합.",
         "- 한국어 질의: 영어 질의를 로컬 Qwen3-VL-4B-Instruct로 번역(greedy). 번역본: qvh/text_ko/translations.jsonl",
         "- 번역 예시(앞 8개, 오역 확인용): " + " / ".join(f"「{t['en']}」→「{t['ko']}」" for t in
             [json.loads(l) for l in open(Path(a.text_ko) / "translations.jsonl")][:8]),
         f"- 질의 특징 종류 선택(한국어 val MR-full-mAP, 결과 전 고정한 규칙): {sel.get('selected', '–')} {sel.get('ko_val_mAP', '')}", "",
         "## QVHighlights val", "",
         "| 변형 | 고른 val 언어 | R1@0.5 | R1@0.7 | mAP | 다른 언어 val R1@0.5 / mAP | 학습 시간 |", "|---|---|---|---|---|---|---|"]
    for n, s in st.items():
        b = s["val_brief"]; o = s.get("val_other_brief")
        L.append(f"| {n} | {s['val_lang']} | {b['MR-full-R1@0.5']} | {b['MR-full-R1@0.7']} | {b['MR-full-mAP']} | "
                 f"{(str(o['MR-full-R1@0.5']) + ' / ' + str(o['MR-full-mAP']) + ' (en)') if o else '–'} | {s['train_minutes']}분 |")
    L += ["", "- CLIP 버전 기존 기록(2026-09-29, 같은 코드·seed, 전체 데이터): val R1@0.5 52.58, R1@0.7 35.35, mAP 32.01", "",
          "## 복지 dev (검수 완료 질의, 학습 없음 기준값은 vlm_prelim_dev.md)", "",
          "| 변형 | 전체 R@1 IoU≥0.3 | S 말 | V 화면 | V 화면 글자 | 사용자 질문 |", "|---|---|---|---|---|---|"]
    for n in st:
        L.append(f"| {n} | {r1(n)} | {r1(n, lambda r: r['type'] == 'S')} | {r1(n, lambda r: r['type'] == 'V')} | "
                 f"{r1(n, lambda r: r['type'] == 'V' and r['overlay_text'])} | {r1(n, lambda r: r['origin'] == 'simulated_user')} |")
    L += ["", "예비 실험(학습 없음) 비교값: B2 구간 검색 CLIP 버전(서비스 체크포인트, 서비스 보정 포함) 8%, B3 main 40%, 화면 검색 Qwen3-VL-Emb 25%, 무작위 5%.", "",
          "## 세부 표 (자동 생성)", "", tables.read_text(encoding="utf-8")]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
