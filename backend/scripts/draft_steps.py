"""신청 단계 카드 초안 (자동) → backend/data/steps/<유튜브ID>.json (status: draft) + docs/service/steps_review_<정책>.md (검수용)

정책의 공식 신청 단계(지원 조건 확인 → 서류 준비 → 신청서 작성 → 결과 확인)마다 미리 정한 질의로 그 영상을 n3_vlm 검색해
1위 장면과 VLM verification을 초안으로 둔다. 겹치는 단계는 뒤 단계를 2위 장면으로 바꾼다.
사람이 검수(시간·제목 고치기, 없는 단계는 지우기)한 뒤 status를 reviewed로 바꾼다. 검수 전에는 화면에 「단계 카드 초안」 표시.

    python backend/scripts/draft_steps.py --policy basic-pension
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services")]
from welfare_service import POLICIES, POLICY_OF_HINT

STEP_QUERIES = {   # 시연 전 고정 (2026-11-12)
    "basic-pension": {1: "기초연금 받을 수 있는 대상과 자격 조건", 2: "기초연금 신청할 때 필요한 서류",
                      3: "기초연금 신청서 작성하는 화면", 4: "기초연금 신청 결과 확인"},
    "child-care": {1: "아이돌봄서비스 받을 수 있는 대상", 2: "아이돌봄서비스 신청할 때 필요한 서류",
                   3: "아이돌봄서비스 신청하는 화면", 4: "아이돌봄서비스 신청 결과 확인"},
}
STEP_LABEL = {1: "1단계 · 지원 조건 확인", 2: "2단계 · 서류 준비", 3: "3단계 · 신청서 작성", 4: "4단계 · 결과 확인"}
SHORT = {1: "자격 확인", 2: "서류", 3: "신청서 작성", 4: "결과 확인"}


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def fmt(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--policy", default="basic-pension")
    a = ap.parse_args()
    from ai.features.welfare_search import WelfareSearch
    ws = WelfareSearch(use_vlm=True)
    pol = POLICIES[a.policy]; qs = STEP_QUERIES[a.policy]
    vids = [y for y, v in ws.catalog.items() if POLICY_OF_HINT.get(v["policy_hint"]) == a.policy]
    out_dir = ROOT / "backend/data/steps"; out_dir.mkdir(parents=True, exist_ok=True)
    L = [f"# 신청 단계 카드 초안 검수: {pol['name']} (자동 생성 {time.strftime('%Y-%m-%d %H:%M')} UTC)", "",
         "각 영상의 단계별 장면 초안입니다. 고칠 것: 시작·끝 시간, 제목(짧게), 맞는 장면이 없으면 그 단계 삭제.",
         f"파일: backend/data/steps/<영상ID>.json — 검수 끝나면 `\"status\": \"reviewed\"`로 바꿔 주세요. 질의는 고정: {qs}", ""]
    for y in vids:
        chs, used = [], []
        L += [f"## {ws.catalog[y]['title']} ({y}, {fmt(ws.catalog[y]['duration_sec'])})", "",
              "| 단계 | 장면 | 확인 | P(답함) | P(화면) | 자막 (검수 때 확인) |", "|---|---|---|---|---|---|"]
        for step, q in qs.items():
            mq, qv = ws.encode(q)
            base = ws.n3(y, mq, qv)
            r = ws.rejudge(y, q, base["top"])
            pick = next((i for i, sp in enumerate(r["top"][:3]) if all(overlap(sp, u) < 0.5 * (sp[1] - sp[0]) for u in used)), 0)
            sp = r["top"][pick]; used.append(sp)
            ver = r["verification"][pick] if pick < len(r["verification"]) else "none"
            sub = ws.subtitle_text(y, sp, 160)
            docs = [d["id"] for d in pol["requiredDocs"] if any(w in sub for w in d["name"].replace("(", " ").split()[:2] if len(w) >= 2)]
            chs.append({"id": f"s{step}", "start": round(sp[0], 1), "end": round(sp[1], 1), "title": SHORT[step] + " 장면",
                        "short": SHORT[step], "step": step, "stepLabel": STEP_LABEL[step], "verification": ver,
                        "subtitle": sub, "screenTitle": "", "relatedDocs": docs, "draft": {"query": q, "pAnswer": round(r["p_answer"][pick], 3),
                                                                                          "pScreen": round(r["p_screen"][pick], 3) if pick < len(r["p_screen"]) else None}})
            L.append(f"| {STEP_LABEL[step]} | {fmt(sp[0])}~{fmt(sp[1])} | {ver} | {r['p_answer'][pick]:.2f} | "
                     f"{(r['p_screen'][pick] if pick < len(r['p_screen']) else 0):.2f} | {sub[:90].replace('|', '/')} |")
        (out_dir / f"{y}.json").write_text(json.dumps({"youtubeId": y, "policyId": a.policy, "status": "draft", "chapters": sorted(chs, key=lambda c: c["start"]),
                                                       "generatedAt": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1), encoding="utf-8")
        L.append("")
    p = ROOT / f"docs/service/steps_review_{a.policy}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {p}, 영상 {len(vids)}개")


if __name__ == "__main__":
    main()
