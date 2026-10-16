# 번역 방식별 영상 검색 비교 실험 (+ 자막 검색)

자막이 없는 영상의 영상(visual) 검색에서 한국어 질의를 어떻게 처리할지, 그리고 자막 검색과 영상 검색을 점수로 합치는 것이 의미 있는지 판단하기 위한 실험입니다.
현재 서비스는 한국어 자막이 있으면 자막 검색(MiniLM)만, 없으면 한국어 질의를 영어로 번역한 뒤 Moment-DETR로 검색합니다.

## 요약

| 유형 | 방식 | 평균 IoU | IoU ≥ 0.3 | IoU ≥ 0.5 |
|---|---|---|---|---|
| S (말로 설명) | (d) 자막 검색 (MiniLM, 서비스 구간 보정) | 0.533 | 100% (10/10) | 50% (5/10) |
| S (말로 설명) | (d) 자막 검색 (보정 전 자막 구간) | 0.490 | 70% (7/10) | 40% (4/10) |
| S (말로 설명) | (a) NLLB 번역 + Moment-DETR | 0.182 | 30% (3/10) | 10% (1/10) |
| S (말로 설명) | (b) opus-mt 번역 + Moment-DETR | 0.148 | 30% (3/10) | 10% (1/10) |
| S (말로 설명) | (c) 다국어 CLIP (번역 없음) | 0.119 | 30% (3/10) | 10% (1/10) |
| S (말로 설명) | 상한: (d)와 (c) 중 나은 쪽 | 0.533 | 100% (10/10) | 50% (5/10) |
| S (말로 설명) | 상한: (d)와 (a) 중 나은 쪽 | 0.541 | 100% (10/10) | 50% (5/10) |
| S (말로 설명) | 무작위 기준선 (기댓값) | 0.079 | 13% | 6% |
| V (화면에만 보임) | (d) 자막 검색 (MiniLM, 서비스 구간 보정) | 0.072 | 20% (2/10) | 0% (0/10) |
| V (화면에만 보임) | (d) 자막 검색 (보정 전 자막 구간) | 0.113 | 20% (2/10) | 10% (1/10) |
| V (화면에만 보임) | (a) NLLB 번역 + Moment-DETR | 0.180 | 10% (1/10) | 10% (1/10) |
| V (화면에만 보임) | (b) opus-mt 번역 + Moment-DETR | 0.163 | 10% (1/10) | 10% (1/10) |
| V (화면에만 보임) | (c) 다국어 CLIP (번역 없음) | 0.185 | 30% (3/10) | 0% (0/10) |
| V (화면에만 보임) | 상한: (d)와 (c) 중 나은 쪽 | 0.200 | 40% (4/10) | 0% (0/10) |
| V (화면에만 보임) | 상한: (d)와 (a) 중 나은 쪽 | 0.229 | 30% (3/10) | 10% (1/10) |
| V (화면에만 보임) | 무작위 기준선 (기댓값) | 0.076 | 13% | 5% |
| 전체 | (d) 자막 검색 (MiniLM, 서비스 구간 보정) | 0.303 | 60% (12/20) | 25% (5/20) |
| 전체 | (d) 자막 검색 (보정 전 자막 구간) | 0.302 | 45% (9/20) | 25% (5/20) |
| 전체 | (a) NLLB 번역 + Moment-DETR | 0.181 | 20% (4/20) | 10% (2/20) |
| 전체 | (b) opus-mt 번역 + Moment-DETR | 0.155 | 20% (4/20) | 10% (2/20) |
| 전체 | (c) 다국어 CLIP (번역 없음) | 0.152 | 30% (6/20) | 5% (1/20) |
| 전체 | 상한: (d)와 (c) 중 나은 쪽 | 0.367 | 70% (14/20) | 25% (5/20) |
| 전체 | 상한: (d)와 (a) 중 나은 쪽 | 0.385 | 65% (13/20) | 30% (6/20) |
| 전체 | 무작위 기준선 (기댓값) | 0.078 | 13% | 6% |

- 상한 행은 질의마다 정답을 보고 두 방식 중 나은 쪽을 고른 값으로, 실제로 만들 수 있는 방식이 아니라 융합으로 얻을 수 있는 최대치입니다.
- 번역 품질 (질의 20개, 작성자 판단): (a) NLLB ✅ 5 · ⚠️ 5 · ❌ 10 / (b) opus-mt ✅ 11 · ⚠️ 6 · ❌ 3

### 해석

1. **말로 설명되는 장면(S)은 자막 검색이 압도적입니다.** IoU ≥ 0.3 기준 10/10, IoU ≥ 0.5 기준 5/10으로, 영상 검색 세 방식(3/10, 1/10)과 무작위 기준선보다 훨씬 높습니다. S에서는 서비스의 구간 보정(시작 2초 앞당김, 최소 6초)이 보정 전 자막 구간보다 정답과 더 잘 맞습니다(IoU ≥ 0.3: 7/10 → 10/10). V에서는 반대로 보정 전이 조금 낫습니다.
2. **화면에만 보이는 장면(V)은 어느 방식도 잘 찾지 못합니다.** 자막 검색은 IoU ≥ 0.3 기준 2/10이고, 그것도 화면 내용이 말과 일부 겹친 질의(#10, #15)입니다. 영상 검색도 1~3/10이며 IoU ≥ 0.5는 1개 이하입니다.
3. **번역 품질은 opus-mt가 확실히 낫지만(의미가 틀린 번역 10개 → 3개), Moment-DETR 검색 정확도는 좋아지지 않았습니다.** 병목은 번역보다 Moment-DETR(영어 QVHighlights 데이터 학습, 1위 구간이 평균 13~20초로 김)입니다. 다국어 CLIP(c)은 V에서 대략 맞는 구간(IoU ≥ 0.3)을 가장 많이 찾았지만 정확한 구간은 0개입니다.
4. **융합으로 얻을 수 있는 최대치가 작습니다.** 질의마다 자막과 영상 중 나은 쪽을 고르는 상한조차 S에서는 적중 수가 자막만 쓸 때와 같습니다. V에서만 늘어나는데, (d)+(c) 상한은 IoU ≥ 0.3 기준 2/10 → 4/10(IoU ≥ 0.5는 0개 그대로), (d)+(a) 상한은 3/10, IoU ≥ 0.5 1/10입니다. 반면 점수 융합이 S 질의의 자막 1위를 영상 결과로 바꾸면 정확도가 떨어질 수 있습니다.

**결론:** 지금 영상 검색 품질로는 점수 융합(α·자막 + (1−α)·영상)의 이득보다 위험이 큽니다. 융합보다 (1) 영상 검색 자체 개선(다국어 CLIP 구간 정교화 또는 한국어 질의에 맞는 모델), (2) 질의 수를 늘린 평가셋 구축이 먼저입니다. 융합을 시험한다면 기본값 off를 유지하고 α를 높게(자막 위주) 두는 것이 안전합니다.

## 실험 설정

- 영상: 로컬 한국어 테스트 영상 4개 — 두부 165초, 스쿼트 42초, 다이소 32초, 주방 37초 (YouTube 다운로드 없음, `ai/experiments/korean_ai_handoff/.../02_Korean_Video_Test`의 영상)
- 영상 feature: CLIP ViT-B/32, 2초 단위 (서비스와 같은 `build_feature`)
- (a) `facebook/nllb-200-distilled-600M` 번역 (`backend/services/translate.py`의 `to_english`) → `predict_moments_hybrid` 1위 구간
- (b) `Helsinki-NLP/opus-mt-ko-en` 번역 → 같은 `predict_moments_hybrid` 1위 구간
- (c) `sentence-transformers/clip-ViT-B-32-multilingual-v1`: 한국어 질의를 그대로 벡터로 만들어 2초 단위 프레임 feature와 코사인 유사도 비교. 구간 선택은 저장소의 `_refine_visual_start`와 같은 규칙(유사도 평활화 → 상위 8개 구간 → 연속 구간 중 (길이, 평균 유사도)가 가장 큰 것)을 영상 전체에 적용. Moment-DETR는 단어 단위 영어 CLIP 입력이 필요해 다국어 문장 벡터를 넣을 수 없으므로 사용하지 않음
- (d) 서비스와 같은 Whisper(`small`) 자막 + fine-tuned MiniLM (SCENEFINDER_MINILM_MODEL_PATH)의 1위 자막 구간. 서비스처럼 시작을 2초 앞당기고 최소 6초로 늘린 구간으로 판정하고, 보정 전 구간 결과도 함께 표시. 자막 문장 수: 두부 57개(ko), 스쿼트 12개(ko), 다이소 18개(ko), 주방 24개(ko)
- 판정: 1위 구간과 정답 구간의 IoU ≥ 0.3, IoU ≥ 0.5. 정답이 여러 구간이면(#10, #11) 가장 높은 IoU 사용
- 무작위 기준선: 영상마다 정답 구간 평균 길이(두부 13.1초, 스쿼트 5.0초, 다이소 3.6초, 주방 3.5초)의 구간을 무작위 위치에 100번 뽑아 평균 IoU와 적중률 계산 (seed 0)
- 1위 구간 평균 길이: (a) 19.7초, (b) 13.1초, (c) 8.6초, (d) 6.4초
- 환경: NVIDIA RTX A5000

## 질의별 결과

구간 옆 괄호는 IoU입니다. **✓.5** = IoU ≥ 0.5, ✓.3 = IoU ≥ 0.3. 번역 품질 표시(✅ 의미 보존 · ⚠️ 일부 누락/부정확 · ❌ 의미가 틀림)는 작성자 판단입니다.

| # | 영상 | 유형 | 질의 | 정답 | (a) NLLB 번역 | (b) opus-mt 번역 | (a) 1위 | (b) 1위 | (c) 1위 | (d) 자막 1위 [보정 전 IoU] | 무작위 평균 IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 두부 | S | 두부를 반으로 자르는 장면 | 13–19초 | ⚠️ The scene of him cutting two parts in half. | ✅ Cut tofu in half | 12–48초 (0.17) | 102–121초 (0.00) | 14–26초 (0.38) ✓.3 | 11–17초 (0.48) ✓.3 [0.54]<br>“먼저 두부 한 모를 준비해주세요 두부는 먼저 반으로” | 0.02 |
| 2 | 두부 | S | 끓는 물에 소금 두 숟가락을 넣는 장면 | 45–50초 | ✅ Two spoons of salt in boiling water. | ✅ Adding two spoons of salt to boiling water | 102–116초 (0.00) | 100–116초 (0.00) | 52–62초 (0.00) | 43–49초 (0.49) ✓.3 [0.30]<br>“여기에 소금 2 숟가락을 넣어주세요” | 0.03 |
| 3 | 두부 | S | 다진 마늘과 대파로 양념을 준비하는 장면 | 98–111초 | ❌ They're preparing a meal with needles and a bunch of them. | ✅ Preparing the seasoning with chopped garlic and onions | 50–163초 (0.12) | 100–121초 (0.45) ✓.3 | 38–44초 (0.00) | 96–104초 (0.43) ✓.3 [0.50]<br>“물기를 빼는 동안 두부 위에 끼얹을 양념을 준비해 ” | 0.07 |
| 4 | 두부 | S | 진간장과 참기름을 넣는 장면 | 127–131초 | ❌ The scene of the intersection and the inclusion of palm oil. | ⚠️ Adding a soy sauce and true oil | 120–146초 (0.16) | 98–118초 (0.00) | 56–62초 (0.00) | 125–131초 (0.56) **✓.5** [0.74]<br>“여기에 진간장 한 숟가락을 넣어주세요. 그리고 참기” | 0.03 |
| 5 | 두부 | V | 노란 도마 위에 썰어둔 두부가 놓여 있는 장면 | 22–36초 | ❌ A scene of two couples lying on a yellow dome. | ⚠️ Two slices on a yellow board | 130–158초 (0.00) | 100–119초 (0.00) | 12–24초 (0.08) | 11–17초 (0.00) [0.00]<br>“먼저 두부 한 모를 준비해주세요 두부는 먼저 반으로” | 0.06 |
| 6 | 두부 | V | 뚜껑 덮인 냄비 앞에서 요리사가 손짓하며 말하는 장면 | 63–92초 | ⚠️ I saw a chef clap his hands in front of a covered pot. | ✅ A cook waving and talking in front of a covered pot | 66–88초 (0.75) **✓.5** | 150–166초 (0.00) | 78–90초 (0.41) ✓.3 | 159–165초 (0.00) [0.00]<br>“팔로우 해두시면 요리할 때 실패하지 않도록” | 0.08 |
| 7 | 두부 | V | 완성된 두부 요리 접시를 들고 보여주는 장면 | 144–165초 | ❌ A scene of me holding a two-piece cookware plate. | ✅ Bringing the finished tofu dish and showing it | 66–91초 (0.00) | 140–164초 (0.82) **✓.5** | 158–165초 (0.33) ✓.3 | 3–9초 (0.00) [0.00]<br>“순식간에 정말 맛있는 두부 요리 하나가 완성돼요” | 0.03 |
| 8 | 스쿼트 | S | 발을 어깨너비로 벌리는 장면 | 3–8초 | ❌ The scene of her feet bending over her shoulders. | ⚠️ Spreading your feet with your shoulders. | 8–17초 (0.00) | 10–20초 (0.00) | 22–28초 (0.00) | 2–8초 (0.73) **✓.5** [0.80]<br>“먼저, 발을 어깨너비 정도로 벌려줘, 발은 살짝 바” | 0.11 |
| 9 | 스쿼트 | S | 뒤꿈치가 바닥에서 떨어지지 않게 설명하는 장면 | 22–30초 | ❌ A scene that explains how the hips don't fall off the floor. | ✅ Show not letting the heel fall off the floor | 32–39초 (0.00) | 6–17초 (0.00) | 14–20초 (0.00) | 25–33초 (0.43) ✓.3 [0.26]<br>“이때, 발의 뒷꿈치는 떨어지면 안 돼. 무릎이 살짝” | 0.16 |
| 10 | 스쿼트 | V | 두 팔을 앞으로 뻗고 옆모습으로 앉는 장면 | 12–17초, 30–38초 | ✅ I see him stretching his arms forward and sitting sideways. | ❌ He's sitting next to me with his arms outstretched. | 0–7초 (0.00) | 0–3초 (0.00) | 14–20초 (0.38) ✓.3 | 28–34초 (0.39) ✓.3 [0.43]<br>“무릎이 살짝 앞으로 나오면서 엉덩이를 앉아주면돼” | 0.23 |
| 11 | 스쿼트 | V | 발 위치를 빨간 점으로 표시한 장면 | 6–8초, 24–26초 | ✅ It's a scene with a red dot on the foot. | ✅ The position of the foot is marked by a red dot | 22–34초 (0.17) | 26–33초 (0.00) | 22–30초 (0.25) | 31–37초 (0.00) [0.00]<br>“체중은 항상 발바닥 중앙이 오게 해줘” | 0.10 |
| 12 | 다이소 | S | 여행용 파우치를 소개하는 장면 | 3–8초 | ❌ A scene from the introduction of a traveling couch. | ❌ Introducing a travel patch | 22–32초 (0.00) | 22–32초 (0.00) | 4–16초 (0.31) ✓.3 | 0–6초 (0.40) ✓.3 [0.29]<br>“빠르게 소개해 드릴게요 매운갈 때 무조건 챙기는 파” | 0.11 |
| 13 | 다이소 | S | 고기 먹을 때 쓰는 양념 세트를 소개하는 장면 | 8–14초 | ⚠️ And this is a presentation of a set of soups that we use when we eat meat. | ✅ Introducing the seasoning set for eating meat | 6–16초 (0.66) **✓.5** | 6–15초 (0.70) **✓.5** | 8–20초 (0.50) **✓.5** | 6–12초 (0.58) **✓.5** [0.27]<br>“고기 먹을 때 필수인 양념세트” | 0.10 |
| 14 | 다이소 | V | 불판 위에서 고기가 구워지는 장면 | 12–14초 | ⚠️ The scene of the meat being cooked on the fireplace. | ⚠️ The roasting of the meat on the fireboard. | 6–15초 (0.23) | 6–15초 (0.24) | 8–18초 (0.20) | 5–11초 (0.00) [0.00]<br>“이제 이거 하나는 끝이에요 고기 먹을 때 필수인 양” | 0.07 |
| 15 | 다이소 | V | 손등에 립 제품을 발라 색을 비교하는 장면 | 21–23초 | ❌ I'm comparing the color of the lipstick on the flashlight. | ✅ A color comparison with a lip on the back of the hand | 18–27초 (0.23) | 18–27초 (0.23) | 16–26초 (0.20) | 19–25초 (0.33) ✓.3 [0.70]<br>“다이소 립 중에는 제일 잘 쓰게 되더라고요” | 0.03 |
| 16 | 다이소 | V | 토토로 인형 옆에 시계가 놓인 장면 | 29–32초 | ✅ The clock next to the Totoro doll. | ✅ The watch next to the Totoro doll. | 16–29초 (0.03) | 18–29초 (0.00) | 4–12초 (0.00) | 0–6초 (0.00) [0.00]<br>“빠르게 소개해 드릴게요” | 0.05 |
| 17 | 주방 | S | 가위로 소스를 짜는 장면 | 6–11초 | ❌ The scene of the sauce being baked. | ❌ Sweeping the gas source | 4–17초 (0.40) ✓.3 | 20–38초 (0.00) | 16–22초 (0.00) | 4–10초 (0.57) **✓.5** [0.42]<br>“이 가위로 소스 짜는거 진짜 편해요” | 0.09 |
| 18 | 주방 | S | 소쿠리에 쌀을 씻는 장면 | 29–34초 | ⚠️ We're washing rice at the Sokuri. | ⚠️ Washing rice in Sokuri | 22–38초 (0.33) ✓.3 | 22–38초 (0.32) ✓.3 | 16–22초 (0.00) | 27–35초 (0.66) **✓.5** [0.81]<br>“세 번째. 이런 물 뿜먹이 있어서 쌀 씻으면 한 톨” | 0.08 |
| 19 | 주방 | V | 떡볶이 위에 빨간 소스를 뿌리는 장면 | 10–12초 | ❌ The scene of a red sauce sprinkled on a cockroach. | ⚠️ Sprinkling red sauce on top of it. | 2–15초 (0.16) | 2–15초 (0.16) | 26–37초 (0.00) | 20–26초 (0.00) [0.00]<br>“시금치 대치고” | 0.08 |
| 20 | 주방 | V | 여자가 냉장고 앞에 서 있는 장면 | 0–2초 | ✅ A woman standing in front of the refrigerator. | ✅ A woman standing in front of a refrigerator. | 0–9초 (0.22) | 0–11초 (0.19) | 32–37초 (0.00) | 10–16초 (0.00) [0.00]<br>“집게 필요할땐 집게로” | 0.02 |

## 재현 방법

프로젝트 루트에서, 백엔드 가상환경과 `backend/.env`(`SCENEFINDER_MINILM_MODEL_PATH` 포함)를 준비한 상태로 실행합니다.

    python ai/experiments/translation_compare/run.py --out /tmp/translation_compare
    python ai/experiments/translation_compare/make_report.py --results /tmp/translation_compare/results.json

- 질의·정답 구간·번역 품질 판단은 `ai/experiments/translation_compare/queries.py`에 있습니다.
- `run.py`는 영상 feature(`.pt`), Whisper 자막, `results.json`을 `--out` 폴더(기본: 시스템 임시 폴더)에 저장합니다. **저장소 안 폴더를 `--out`으로 지정하지 마세요.** feature 파일은 저장소에 넣지 않습니다.
- 테스트 영상은 `data/raw/korean_test/`에 있으면 그것을, 없으면 `ai/experiments/korean_ai_handoff/remaining_176_files/02_Korean_Video_Test/`(Git LFS)의 영상을 사용합니다.
- `Helsinki-NLP/opus-mt-ko-en` 모델은 처음 실행할 때 HuggingFace에서 내려받습니다(약 300MB). 다국어 CLIP은 `ai/experiments/korean_ai_handoff/model_assets/multilingual_clip/`의 로컬 모델을 씁니다.
- GPU 기준 전체 실행에 수 분 걸립니다. 같은 입력이면 같은 결과가 나옵니다(무작위 기준선 seed 고정).

## 한계

- 질의 20개, 영상 4개로 규모가 작습니다. 영상 검색 방식 간 차이는 1~2건이라 통계적으로 의미 있는 차이로 보기 어렵습니다.
- 정답 구간은 프레임을 2~8초 간격으로 보고 한 사람이 정한 대략값입니다.
- (c)의 구간 선택 규칙은 기존 보정 로직을 그대로 쓴 것으로, 이 실험을 위해 조정하지 않았습니다. 상위 8개 구간 기준이라 1위 구간이 최대 16초입니다.
- 상한 행은 정답을 보고 고른 값이라 실제 융합 성능은 이보다 낮습니다.
