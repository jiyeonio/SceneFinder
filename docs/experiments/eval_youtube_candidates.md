# 분석했던 YouTube 영상으로 평가셋 만들기

서비스에서 이미 분석한 YouTube 영상 중 평가에 쓸 영상을 고르고, 영상별로 무엇이 남아 있는지 정리했습니다.
라벨링은 [tools/labeler](../../tools/labeler/README.md)의 YouTube 재생 모드로 하고, 실험 실행에 필요한 mp4는 따로 받아 둡니다.

## 남아 있는 것 (2026-10-16 기준)

영상별 전체 목록: [analyzed_youtube_inventory.tsv](analyzed_youtube_inventory.tsv) (226개)

| 항목 | 영상 수 | 위치 |
|---|---|---|
| Whisper 자막 | 226 / 226 | `data/processed/subtitles/<ID>.json` |
| CLIP feature (2초 단위) | 56 / 226 | `data/features/<ID>_clip_features.pt` |
| mp4 | **0 / 226** | 서비스가 분석 후 영상 파일을 지움 (`indexer.py`) |

- feature가 있는 56개 중 49개는 한국어 자막이 없는 영상입니다(말이 없거나 외국어). 서비스가 한국어 자막이 있으면 feature 추출을 건너뛰기 때문입니다. 나머지 170개는 한국어 자막만 있습니다.
- `data/features`의 나머지 8개(`fast_cold`, `video_001` 등)는 속도 측정용 로컬 파일이라 YouTube 영상이 아닙니다.
- 길이 분포는 2분 미만 112개(대부분 쇼츠), 2~15분 100개, 15분 초과 14개입니다.
- 분야는 검색했던 주제를 따라 요리(김치찌개·된장찌개·두부조림·계란말이 등)와 에어팟 리뷰, 축구, 피아노, 방 꾸미기, 배스낚시가 대부분입니다. **운동(홈트·스트레칭) 영상은 없습니다.**
- 제목·길이·분류·임베드 가능 여부는 YouTube Data API `videos.list`로 조회했습니다. 영상은 받지 않았습니다. 14개는 임베드를 막아 두어 라벨링 도구로 재생할 수 없습니다.
- 말 양은 30초 넘는 자막 구간을 뺀 분당 글자 수로 나눴습니다: 많음 300자 이상, 중간 100~300자, 적음 50~100자, 거의 없음 50자 미만. 30초 넘는 자막 구간이 있는 영상이 29개 있고, 그중에는 말이 없는 구간 전체를 Whisper가 한 문장으로 만든 경우가 있어서(예: 먹방 영상의 24–473초 "잘먹었습니다") 자막 구간 길이를 그대로 합하면 말 양이 실제보다 크게 나옵니다.

## 추천 영상 12개

라벨링 도구용 목록: [eval_youtube_videos.tsv](eval_youtube_videos.tsv) (`--youtube-list`로 읽음, 키·분야가 미리 채워짐)

| # | 키 | YouTube ID | 길이 | 분야 | 말 양 | 남아 있는 것 | 고른 이유 |
|---|---|---|---|---|---|---|---|
| 1 | airpods_review | `36h_8hJiO50` | 6:06 | 리뷰 | 많음 | 자막 | 제품 리뷰 |
| 2 | battery_lecture | `HsV9CMmEvFo` | 15:01 | 강의 | 많음 | 자막 | 설명 위주 강의형, 가장 긴 영상 |
| 3 | eggroll_paik | `T7YJviWhquo` | 7:52 | 요리 | 많음 | 자막 | 요리 과정을 말로 설명 (S 질의 기준선) |
| 4 | room_vlog | `VIPlJ-u0nOw` | 8:45 | 브이로그 | 많음 | 자막 | 실내 브이로그 |
| 5 | tofu_braise | `x54thOO7NHU` | 3:27 | 요리 | 중간 | 자막 | 3분대 요리 |
| 6 | wc_goals | `OSEFivkqPtc` | 7:14 | 스포츠 | 중간 | 자막 | 골 장면 모음과 해설 (동작 위주) |
| 7 | ag_final | `iSHVe7ozhEk` | 3:01 | 스포츠 | 중간 | 자막 | 경기 하이라이트 (동작 위주) |
| 8 | steak_camp | `05f8sG4OhZs` | 14:42 | 요리 | 없음 | 자막(빈), feature | 말 없는 긴 영상, 서비스에서는 영상 검색 경로 |
| 9 | airpods_fake | `ynXCtZHoGXk` | 9:44 | 리뷰 | 없음 | 자막(빈), feature | 말 없이 화면으로 비교 |
| 10 | mukbang_chicken | `dvlV6iA3UaA` | 7:54 | 먹방 | 거의 없음 | 자막 | 처음 20초만 말함. 자막 검색이 엉뚱한 긴 구간을 낼 수 있는 사례 |
| 11 | piano_canon | `2qtKMC5wzkU` | 5:31 | 음악 | 없음 | 자막(빈), feature | 연주 영상 |
| 12 | tofu_silent | `9fmd1LOTa-E` | 2:40 | 요리 | 없음 | 자막(빈), feature | 기존 두부 영상과 같은 요리를 말 없이 |

- 말 많음 4개, 말 중간(동작 위주) 3개, 말 없음·거의 없음 5개입니다. 지금 평가셋(로컬 4개)은 모두 말이 많은 1분 안팎 영상이라 말 없는 쪽을 많이 넣었습니다.
- 길이는 2:40~15:01이고, 4분 미만 3개, 5~10분 7개, 약 15분 2개입니다.
- 운동 영상은 분석된 영상 중에 없어서 넣지 못했습니다. 기존 로컬 `kr_squat_001`(42초)이 유일합니다. 운동 분야가 필요하면 새 영상 1~2개를 따로 정해야 합니다.
- 요리가 4개(+먹방 1개)로 많은 것은 분석된 영상 자체가 요리 위주이기 때문입니다.
- 화면 내용은 아직 보지 않고 제목·자막 통계로 골랐습니다. 라벨링하면서 질의를 5개 이상 만들기 어려운 영상은 [인벤토리](analyzed_youtube_inventory.tsv)에서 같은 조건의 다른 영상으로 바꾸세요.

## mp4를 받아야 하는 영상

12개 **모두 mp4가 없습니다.** 라벨링은 YouTube 재생으로 할 수 있지만, `run.py`·`captions.py`는 영상 파일에서 CLIP feature·VLM 설명문·Whisper 자막을 만들므로 실험하려면 mp4가 필요합니다.

    36h_8hJiO50  HsV9CMmEvFo  T7YJviWhquo  VIPlJ-u0nOw  x54thOO7NHU  OSEFivkqPtc
    iSHVe7ozhEk  05f8sG4OhZs  ynXCtZHoGXk  dvlV6iA3UaA  2qtKMC5wzkU  9fmd1LOTa-E

- 서버에서는 받지 않습니다(서버 IP가 YouTube 봇 확인에 걸려 있음). PC에서 받아 `~/scenefinder_eval/videos/<YouTube ID>.mp4`로 올립니다.
- **자르지 말고 전체 영상**을 받으세요. 라벨링 도구에서 찍은 시간은 YouTube 재생 시간 기준이라, 앞부분이 잘리면 정답 구간이 어긋납니다.
- 화질은 480p 이상, H.264(mp4)를 권장합니다. 서비스는 480p 이하로 받지만, VLM 설명문은 긴 변 640px로 줄여 쓰므로 480p면 충분합니다.
- 파일 이름이 `<YouTube ID>.mp4`이면 실험 스크립트가 라벨의 `youtube_id`로 찾아 씁니다. 다른 폴더를 쓰려면 `SCENEFINDER_EVAL_VIDEO_DIRS`에 지정합니다.
- feature가 있는 4개(#8, #9, #11, #12)도 실험 스크립트는 `--out` 폴더에서 feature를 새로 만듭니다. 기존 feature는 서비스 결과와 비교할 때만 씁니다.
