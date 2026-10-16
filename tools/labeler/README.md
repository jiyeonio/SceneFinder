# 평가 질의 라벨링 도구

로컬 영상이나 YouTube 영상을 브라우저에서 재생하며 질의를 쓰고, 정답 구간의 시작·끝을 버튼(또는 단축키)으로 찍어 JSON으로 저장합니다.
저장한 JSON은 `ai/experiments/translation_compare`의 `run.py`·`captions.py`·`fusion.py`가 `--queries`로 바로 읽습니다.

표준 라이브러리만 쓰므로 따로 설치할 것은 없습니다 (`convert.py from-py`의 영상 길이 확인에만 ffprobe 사용).

## 실행

프로젝트 루트에서:

    # 기존 20개 질의에서 시작하려면 (처음 한 번)
    python tools/labeler/convert.py from-py -o ai/experiments/translation_compare/labels.json

    python tools/labeler/server.py --labels ai/experiments/translation_compare/labels.json \
        --videos data/raw/korean_test [다른 영상 폴더 ...]

http://127.0.0.1:8765 에 접속합니다. 원격 서버에서 실행했다면 VS Code의 포트 포워딩을 쓰거나
`ssh -L 8765:127.0.0.1:8765 <서버>`로 연결합니다. 서버는 기본으로 127.0.0.1에서만 받습니다.

- `--videos`를 생략하면 `data/raw/korean_test`와 `~/scenefinder_eval/videos` 중 있는 폴더를 씁니다.
- `--labels` 파일이 없으면 빈 세트로 시작하고, 첫 저장 때 만듭니다.
- 질의를 저장·수정·삭제할 때마다 바로 파일에 씁니다. 이전 내용은 `<labels>.bak`으로 남습니다.
- 저장이 실패하면 상단에 빨간 글씨로 표시됩니다. 이때는 「JSON 내려받기」로 백업하세요.
- 영상 파일은 저장소에 넣지 않습니다(`.gitignore`의 `*.mp4`). 라벨 JSON에는 경로만 기록합니다.

## YouTube 영상 라벨링

mp4가 없어도 YouTube 임베드로 재생하며 라벨링할 수 있습니다.

    python tools/labeler/server.py --labels ai/experiments/translation_compare/labels.json \
        --youtube-list docs/experiments/eval_youtube_videos.tsv [--youtube 영상ID ...]

- `--youtube-list`: 머리행에 `youtube_id`가 있는 TSV(선택 열: `key`, `title`, `domain`은 영상 정보에 미리 채워짐) 또는 한 줄에 ID 하나인 텍스트 파일.
- 페이지 왼쪽 위 입력칸에 YouTube 주소(`watch?v=`, `youtu.be/`, `shorts/`)나 ID를 넣어 바로 추가할 수도 있습니다.
- 재생은 **사용자 브라우저에서** YouTube로 합니다. 서버는 영상을 받지 않습니다.
- 라벨에는 `youtube_id`만 저장합니다(`file` 없음). 실험 스크립트는 `~/scenefinder_eval/videos/<ID>.mp4`를 찾아 씁니다. 폴더는 `SCENEFINDER_EVAL_VIDEO_DIRS`로 바꿀 수 있습니다.
- `--videos` 폴더에 `<ID>.mp4`가 있으면 같은 항목에 「파일」 표시가 붙고, 재생을 YouTube ↔ 로컬 파일로 바꿀 수 있습니다. 받은 mp4가 YouTube와 시간이 맞는지 확인할 때 씁니다.
- 찍은 시간은 YouTube 재생 시간 기준입니다. 나중에 받는 mp4는 앞뒤를 자르지 않은 전체 영상이어야 합니다.
- 업로더가 임베드를 막은 영상은 재생되지 않고 오류 문구가 나옵니다([인벤토리](../../docs/experiments/analyzed_youtube_inventory.tsv)의 `임베드` 열).
- YouTube 화면을 클릭해도 키보드 포커스를 이 페이지로 되돌리므로 단축키는 계속 동작합니다. YouTube 자체 단축키는 꺼 두었습니다.

## 사용법

1. 왼쪽에서 영상을 고르고, 영상 정보(키·표시 이름·분야)를 적습니다. 키는 결과 파일 이름(`bench_<키>`)에 쓰이므로 영문·숫자·`_`·`-`만 쓰고, 영상마다 달라야 합니다.
2. 유형을 고릅니다. **S** = 말(자막)로 설명되는 장면, **V** = 말로는 안 나오고 화면에만 보이는 장면.
3. 질의를 쓰고, 정답 구간의 시작에서 `[`, 끝에서 `]`를 누른 뒤 「구간 추가」(또는 `Enter`)를 누릅니다. 같은 장면이 여러 번 나오면 구간을 여러 개 추가합니다(판정은 가장 높은 IoU).
4. 「질의 저장」을 누릅니다. 찍어 두고 추가하지 않은 구간이 있으면 함께 추가됩니다.

| 단축키 | 동작 |
|---|---|
| `Space` | 재생 / 정지 |
| `←` `→` | 1초 이동 (`Shift`와 함께 5초) |
| `,` `.` | 0.1초 이동 |
| `[` `]` | 현재 시점을 시작 / 끝으로 |
| `Enter` | 찍은 구간 추가 |
| `Esc` | 입력칸에서 나가기 (입력칸 안에서는 단축키가 동작하지 않음) |

시간은 0.1초 단위로 저장합니다. 목록의 ▶로 저장한 구간만 재생해 확인할 수 있습니다.

### 라벨링 기준 (기존 20개와 맞추기)

- 질의는 "~하는 장면"처럼 사용자가 검색창에 쓸 법한 한 문장으로 씁니다.
- S 질의는 말 내용과 겹치게 쓰되, 자막 문장을 그대로 베끼지 않습니다.
- V 질의는 그 구간에서 그 내용을 말로 하지 않는 장면만 고릅니다. 화면에 덧씌운 글자만 보고 찾을 수 있는 장면이면 메모에 적어 둡니다.
- 정답 구간은 장면이 시작해서 끝날 때까지로 잡습니다. 같은 내용을 말하는 앞뒤 구간은 넣지 않습니다.

## 저장 형식

    {
      "format": "scenefinder-labels/1",
      "videos": {
        "tofu": {"file": "data/raw/korean_test/kr_tofu_001.mp4", "name": "두부", "domain": "요리", "duration": 165.0}
      },
      "queries": [
        {"num": 1, "video": "tofu", "type": "S", "query": "두부를 반으로 자르는 장면", "gt": [[13, 19]], "note": "선택"}
      ]
    }

- `file`: 저장소 안이면 루트 기준 상대 경로, 밖이면 절대 경로. 실험 스크립트는 이 경로에 없으면 `data/raw/korean_test/<파일명>`에서도 찾습니다.
- `youtube_id`: YouTube 영상이면 `file` 대신 저장합니다. 예: `"steak_camp": {"youtube_id": "05f8sG4OhZs", "name": "야외 스테이크", "domain": "요리", "title": "…", "duration": 882.0}`
- `num`: 세트 안에서 고유한 번호입니다. 새 질의는 가장 큰 번호 + 1을 받고, 삭제해도 다른 번호는 바뀌지 않습니다.
- `handoff`(선택): 인수인계 폴더의 원래 파일명입니다. `from-py`로 만든 기존 영상에만 있습니다.

## 변환

    # 라벨 JSON → queries.py 형식 (VIDEO_FILES, VIDEO_NAMES, QUERIES)
    python tools/labeler/convert.py to-py labels.json -o 새_queries.py

    # 기존 queries.py → 라벨 JSON
    python tools/labeler/convert.py from-py -o labels.json

실험 스크립트는 JSON을 직접 읽으므로 `to-py`는 queries.py 자체를 새 세트로 바꿀 때만 필요합니다.
번역 품질(`TRANSLATION_QUALITY`)과 VLM 결과 판단(`VLM_V_ANALYSIS`)은 작성자 판단이라 변환하지 않습니다.

## 실험에 쓰기

    python ai/experiments/translation_compare/run.py      --out /tmp/eval_v2 --queries ai/experiments/translation_compare/labels.json
    python ai/experiments/translation_compare/captions.py --out /tmp/eval_v2 --queries ai/experiments/translation_compare/labels.json   # 선택
    python ai/experiments/translation_compare/fusion.py   --out /tmp/eval_v2   # run.py가 쓴 질의 세트를 그대로 사용

- 새 세트는 새 `--out` 폴더를 쓰세요. feature·자막 캐시는 `bench_<키>` 이름이라 같은 폴더에서 같은 키를 다른 영상에 쓰면 잘못된 캐시를 읽습니다.
- 말소리가 없는 영상은 (d) 자막 검색 결과 없이 평가됩니다.
- `make_report.py`는 아직 queries.py의 기존 20개 질의 기준입니다.
