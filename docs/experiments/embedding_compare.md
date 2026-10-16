# 임베딩 모델 비교: 자막 검색(d)·설명문 검색(e) (dev)

평가셋 v2의 **dev 영상 6개**에서 자막 검색(d)과 설명문 검색(e)의 임베딩 모델만 바꿔 비교했습니다. 자막(Whisper small)·설명문(Qwen3-VL-4B, 1장씩 처리)·검색 방식(연속 1~3문장 창, 코사인 유사도, 서비스 구간 보정)은 [eval_v2.md](eval_v2.md)와 같고 임베딩 모델만 다릅니다. test 영상은 쓰지 않았습니다.

## 자막 검색 (d)

각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / R@3 (개수, 평균 IoU)

| 모델 | 검수된 S (n=14) | 검수된 V (n=33) | 말 내용 S (AI 초안, 미검수) (n=13) |
|---|---|---|---|
| fine-tuned MiniLM (서비스 현재) | 5 / 3 / 7 (0.19) | 0 / 0 / 0 (0.00) | 6 / 4 / 9 (0.29) |
| BAAI/bge-m3 | 5 / 3 / 5 (0.21) | 0 / 0 / 0 (0.00) | 9 / 5 / 9 (0.43) |
| intfloat/multilingual-e5-large | 4 / 2 / 6 (0.16) | 0 / 0 / 0 (0.01) | 8 / 6 / 10 (0.41) |

## 설명문 검색 (e)

각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / R@3 (개수, 평균 IoU)

| 모델 | 검수된 S (n=14) | 검수된 V (n=33) | 말 내용 S (AI 초안, 미검수) (n=13) |
|---|---|---|---|
| fine-tuned MiniLM (서비스 현재) | 3 / 1 / 3 (0.11) | 3 / 1 / 10 (0.09) | 2 / 0 / 7 (0.08) |
| BAAI/bge-m3 | 2 / 1 / 6 (0.17) | 5 / 1 / 11 (0.12) | 2 / 0 / 4 (0.09) |
| intfloat/multilingual-e5-large | 2 / 0 / 3 (0.14) | 7 / 1 / 11 (0.13) | 2 / 0 / 4 (0.10) |

## 검색 시간과 GPU 메모리

| 모델 | 모델 로딩 | 색인 (dev 영상 전체, 자막+설명문) | 질의 1개 검색 (평균 / 95%) | GPU 메모리 (로딩 후 / 최대) |
|---|---|---|---|---|
| fine-tuned MiniLM (서비스 현재) | 4.9초 | 2.8초 (창 5,874개) | 7 / 7 ms | 449 / 614 MiB |
| BAAI/bge-m3 | 6.4초 (첫 실행 214초, 다운로드 포함) | 33.1초 (창 5,874개) | 13 / 13 ms | 2,166 / 2,796 MiB |
| intfloat/multilingual-e5-large | 6.7초 (첫 실행 184초, 다운로드 포함) | 33.8초 (창 5,874개) | 13 / 13 ms | 2,136 / 2,773 MiB |

- GPU 메모리는 torch가 할당한 최댓값(`torch.cuda.max_memory_allocated`)입니다. 색인할 때 64개씩 묶어 임베딩합니다.
- 검색 시간은 질의 임베딩 + 영상 하나의 창 전체와 유사도 계산 + 정렬입니다(색인은 미리 만들어 둔 상태).
- 환경: NVIDIA RTX A5000

## 해석

1. **말 내용을 찾는 질의에서는 큰 다국어 모델이 자막 검색을 올렸습니다.** 말 내용 S 13개(AI 초안, 미검수)에서 IoU ≥ 0.3이 MiniLM 6개 → bge-m3 9개, e5-large 8개였고 평균 IoU도 0.29 → 0.43·0.41입니다. 다만 13개뿐이고 정답이 아직 검수 전이라 방향만 보는 결과입니다.
2. **검수된 S 14개(대부분 화면 묘사 말투)에서는 차이가 없었습니다(4~5개).** 자막에 그 장면을 묘사하는 말이 없으면 모델을 바꿔도 찾을 수 없습니다. V에서 자막 검색은 세 모델 모두 거의 0입니다.
3. **설명문 검색(e)은 V에서 e5-large 7개, bge-m3 5개, MiniLM 3개(33개 중)로 큰 모델이 조금 낫지만** R@3은 10~11개로 비슷해, 1위 순위가 바뀐 정도입니다. 개수 차이가 2~4개라 우연일 수 있습니다.
4. **비용:** bge-m3·e5-large는 GPU 메모리가 약 2.1~2.8GB로 MiniLM(0.4~0.6GB)의 약 5배, 색인 시간이 약 12배(dev 6개 영상 2.8초 → 33초, 영상 하나당 약 5~6초), 질의 검색이 7ms → 13ms입니다. 영상 분석 1번에 수 초가 더 드는 수준이라 서비스 지연에는 큰 문제가 아니지만, 다른 모델(Whisper·CLIP·Moment-DETR·번역)과 같은 GPU에 올리므로 메모리 여유를 확인해야 합니다.
5. **결정은 미룹니다.** 말 내용 질의를 검수한 뒤 dev에서 다시 비교하고, 고른 모델을 test에서 한 번 확인하는 순서가 맞습니다. fine-tuned MiniLM은 `paraphrase-multilingual-MiniLM-L12-v2`를 한국어 데이터로 추가 학습한 모델이므로([korean_minilm](../../ai/experiments/korean_minilm/README.md)), bge-m3를 같은 데이터로 추가 학습하는 방안도 비교할 가치가 있습니다.

## 재현 방법

    python ai/experiments/translation_compare/embedding_compare.py --results ~/scenefinder_eval/results_v2 \
        --queries ~/scenefinder_eval/labels_draft.json --subset dev --out ~/scenefinder_eval/embedding_compare/results.json
    python ai/experiments/translation_compare/embedding_compare.py --report ~/scenefinder_eval/embedding_compare/results.json

- bge-m3·multilingual-e5-large는 처음 실행할 때 Hugging Face에서 내려받습니다(각각 약 2GB).
- fine-tuned MiniLM 결과는 run.py의 (d)·(e) 결과와 같은지 실행할 때 확인합니다(`minilm_matches_run`).
