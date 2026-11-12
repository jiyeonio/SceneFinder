"""시연 질문 시험: 시연 영상 세트에서 질문마다 n3_vlm으로 상위 장면·verification·공식 정보 답을 표로 → docs/service/demo_query_test.md

    python backend/scripts/demo_queries.py
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services")]
from welfare_service import POLICIES, Searcher

# (번호, 질문, 맥락 정책, 대안 2개) — 대안은 시험 전에 정해 둔 것
QUESTIONS = [
    ("1", "기초연금 신청할 때 뭐 챙겨가야 돼요?", None, ["기초연금 신청 서류 뭐 필요해요?", "기초연금 구비서류 목록 보여줘"]),
    ("2", "기초연금 신청하는 법", None, ["기초연금 온라인으로 신청하는 방법", "기초연금 신청서 작성하는 화면"]),
    ("3", "이거 아직 신청 되는 거예요?", "basic-pension", ["기초연금 지금도 신청할 수 있어요?", "기초연금 신청 기간이 언제까지예요?"]),
    ("4a", "월세 지원 받으려면 뭐 내야 돼요?", None, ["청년월세 지원 신청 서류", "청년 월세 지원 어떻게 신청해요?"]),
    ("4b", "아이돌봄 어디서 신청해요?", None, ["아이돌봄서비스 신청 방법", "아이돌봄 신청하는 화면 보여줘"]),
]
VER = {"screen": "화면에서 확인됨", "subtitle": "자막에서 확인됨", "none": "확인 안 됨", "pending": "확인 중"}


def fmt(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def short(v, n=90):
    if isinstance(v, list):
        v = " / ".join(x["name"] if isinstance(x, dict) and "name" in x else (f"{x['label']} {x['value']}" if isinstance(x, dict) else str(x)) for x in v)
    return str(v).replace("\n", " ").replace("|", "/")[:n]


def run(s, q, ctx):
    out = s.start(q, ctx)
    while out["status"] == "pending":
        time.sleep(0.2)
    return out


def main():
    s = Searcher("n3_vlm")
    run(s, "예열", None)
    cat = s.ws.catalog
    L = ["# 시연 질문 시험 (n3_vlm, 시연 영상 14개: dev 8 + 새 영상 6)", "",
         f"자동 생성 {time.strftime('%Y-%m-%d %H:%M')} UTC. 청년 주거 새 영상 4개는 다운로드 403으로 못 받아 청년월세는 dev 영상 1개뿐입니다.",
         "verification·「영상에 답 없음」 규칙은 dev에서 맞추지 않은 값입니다.", ""]
    for num, q0, ctx, alts in QUESTIONS:
        L += [f"## {num}. {q0}" + (f" (맥락: {POLICIES[ctx]['name']})" if ctx else ""), ""]
        for q in [q0] + alts:
            o = run(s, q, ctx)
            L += [f"### 「{q}」 — 정책 {POLICIES[o['policyId']]['name'] if o['policyId'] else '없음'}, 의도 {o['intents'] or '-'}, "
                  f"기본 {o['timing']['base_sec']}초 · VLM 확인 {o['timing'].get('verify_sec')}초"
                  + (" · **영상에 답 없음 안내**" if o["noAnswerInVideo"] else ""), "",
                  "| 순위 | 영상 | 장면 | 확인 | P(답함) | P(화면) | 장면 자막 |", "|---|---|---|---|---|---|---|"]
            for i, v in enumerate(o["videos"]):
                y = v["youtubeId"]; sp = v["top"][0]
                L.append(f"| {i + 1} | {cat[y]['title'][:28]} ({y}) | {fmt(sp[0])}~{fmt(sp[1])} | {VER[v['verification'][0]]} | "
                         f"{v.get('pAnswer', [0])[0]:.2f} | {v.get('pScreen', [0])[0]:.2f} | {short(s.ws.subtitle_text(y, sp), 60)} |")
                for j, sp2 in enumerate(v["top"][1:3]):
                    L.append(f"|  | └ 같은 영상 {j + 2}위 | {fmt(sp2[0])}~{fmt(sp2[1])} | {VER[v['verification'][j + 1]]} | "
                             f"{v.get('pAnswer', [0, 0, 0])[j + 1]:.2f} | {v.get('pScreen', [0, 0, 0])[j + 1]:.2f} | {short(s.ws.subtitle_text(y, sp2), 60)} |")
            off = o["official"]
            if off and off["items"]:
                L += ["", "공식 정보 답 (" + off["source"] + f", {off['baseYear']}년 기준 · 수정 {off['updatedAt']}):"]
                L += [f"- {it['field']}: {short(it['value'], 160)}" for it in off["items"]]
            L.append("")
    out = ROOT / "docs/service/demo_query_test.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
