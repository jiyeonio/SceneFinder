"""평가 질의 세트 읽기: queries.py(기본) 또는 라벨링 도구(tools/labeler)가 저장한 JSON.

JSON 형식 (tools/labeler/README.md 참고)
    {
      "format": "scenefinder-labels/1",
      "videos": {"tofu": {"file": "data/raw/korean_test/kr_tofu_001.mp4", "name": "두부", "domain": "요리"},
                 "steak_camp": {"youtube_id": "05f8sG4OhZs", "name": "야외 스테이크", "domain": "요리"}},
      "queries": [{"num": 1, "video": "tofu", "type": "S", "query": "두부를 반으로 자르는 장면", "gt": [[13, 19]]}]
    }
- file: 저장소 루트 기준 상대 경로 또는 절대 경로
- youtube_id: file이 없으면 EVAL_VIDEO_DIRS에서 <ID>.mp4(.webm/.mkv/.mov/.m4v)를 찾음.
  폴더는 환경변수 SCENEFINDER_EVAL_VIDEO_DIRS(여러 개는 ':'로 구분)로 바꿀 수 있음
- type: S = 말로 설명되는 장면, V = 말로는 안 나오고 화면에만 보이는 장면
- gt: 정답 구간 목록 [[시작초, 끝초], ...] (여러 개면 가장 높은 IoU로 판정)
- source(선택): ai_draft(AI 초안, 미검수) / human_reviewed(AI 초안을 사람이 검수) / human(사람이 처음부터 작성).
  없으면 human으로 봄
- overlay_text(선택): true면 화면에 덧씌운 글자만으로도 찾을 수 있는 장면. 없으면 미표시(None)
- negative_queries(선택): 영상에 없는 장면(정답 없음) 질의. 지금 실험 스크립트는 평가하지 않음

dev/test 나누기: docs/experiments/eval_youtube_videos.tsv의 split 열(YouTube ID 기준). load(..., subset="dev")면
dev 영상의 질의만 씁니다. 설정(규칙·임계값 등)은 dev에서만 정하고 test는 최종 보고에만 씁니다.
"""
import csv
import json
import os
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCAL_VIDEO_DIR = ROOT / "data/raw/korean_test"
HANDOFF_VIDEO_DIR = ROOT / "ai/experiments/korean_ai_handoff/remaining_176_files/02_Korean_Video_Test"
FORMAT = "scenefinder-labels/1"
SOURCES = ("ai_draft", "human_reviewed", "human")
SPLIT_FILE = ROOT / "docs/experiments/eval_youtube_videos.tsv"
SUBSETS = ("dev", "test")


def video_splits(path=SPLIT_FILE):
    """YouTube ID → dev/test."""
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["youtube_id"]: r["split"] for r in csv.DictReader(f, delimiter="\t") if r.get("split")}
VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov", ".m4v")


def eval_video_dirs():
    """YouTube ID로 영상 파일을 찾을 폴더. 서비스가 받는 data/raw도 포함."""
    env = os.getenv("SCENEFINDER_EVAL_VIDEO_DIRS")
    dirs = env.split(os.pathsep) if env else [str(Path.home() / "scenefinder_eval/videos")]
    return [Path(d).expanduser() for d in dirs if d] + [ROOT / "data/raw"]


class QuerySet:
    def __init__(self, source, videos, queries, info=None):
        self.source = source      # 읽은 파일 (결과 meta에 기록)
        # 번호 → {"source": 작성 출처, "overlay_text": True/False/None}
        self.info = info or {q[0]: {"source": "human", "overlay_text": None} for q in queries}
        self.subset = None        # dev/test로 거른 경우
        self.videos = videos      # 키 → {"file": 경로 또는 None, "youtube_id": ID 또는 None, "name": 표시 이름,
                                  #        "handoff": 인수인계 파일명 또는 None}
        self.queries = queries    # [(번호, 영상 키, 유형, 질의, [(시작, 끝), ...])]

    @property
    def video_keys(self):
        """질의가 있는 영상만, 처음 나온 순서대로."""
        return list(dict.fromkeys(key for _, key, _, _, _ in self.queries))

    def name(self, key):
        return self.videos[key].get("name") or key

    def video_path(self, key) -> Path:
        """file이 경로면 그대로(상대 경로는 저장소 루트 기준), 파일명만 있으면 data/raw/korean_test에서 찾습니다.
        못 찾으면 youtube_id로 eval_video_dirs()의 <ID>.<확장자>를, 그다음 인수인계 폴더(있는 경우)를 찾습니다.
        (인수인계 폴더의 한글 파일명은 NFD라 정규화해서 비교) 테스트 영상은 저장소에 포함하지 않습니다."""
        info = self.videos[key]
        candidates = []
        if info.get("file"):
            file = Path(info["file"])
            candidates += [file if file.is_absolute() else ROOT / file, LOCAL_VIDEO_DIR / file.name]
        if info.get("youtube_id"):
            candidates += [d / f"{info['youtube_id']}{ext}" for d in eval_video_dirs() for ext in VIDEO_EXTS]
        for p in candidates:
            if p.exists():
                return p
        if info.get("handoff"):
            want = unicodedata.normalize("NFC", info["handoff"])
            for p in HANDOFF_VIDEO_DIR.glob("*.mp4"):
                if unicodedata.normalize("NFC", p.name) == want:
                    return p
        hint = (f"{eval_video_dirs()[0]}/{info['youtube_id']}.mp4" if info.get("youtube_id") and not info.get("file")
                else str(candidates[0]))
        raise FileNotFoundError(f"영상을 찾을 수 없습니다 ({key}): {hint} 에 두세요")


def _source(path) -> str:
    """결과 meta에 남길 경로: 저장소 안이면 루트 기준 상대 경로."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _from_module():
    import queries as q

    youtube = getattr(q, "VIDEO_YOUTUBE", {})
    videos = {k: {"file": local, "name": q.VIDEO_NAMES.get(k, k), "handoff": handoff, "youtube_id": youtube.get(k)}
              for k, (local, handoff) in q.VIDEO_FILES.items()}
    queries = [(num, key, typ, ko, [tuple(g) for g in gts]) for num, key, typ, ko, gts in q.QUERIES]
    return QuerySet(_source(q.__file__), videos, queries)


def _from_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path}: format이 {FORMAT!r}가 아닙니다")
    videos = {}
    for k, v in data["videos"].items():
        if not v.get("file") and not v.get("youtube_id"):
            raise ValueError(f"{path} 영상 {k}: file 또는 youtube_id가 필요합니다")
        videos[k] = {"file": v.get("file"), "youtube_id": v.get("youtube_id"), "name": v.get("name") or k,
                     "handoff": v.get("handoff")}
    queries, seen, info = [], set(), {}
    for item in data["queries"]:
        num, key, typ, ko = int(item["num"]), item["video"], item["type"], item["query"].strip()
        gts = [(float(a), float(b)) for a, b in item["gt"]]
        problems = []
        if num in seen:
            problems.append("번호 중복")
        if key not in videos:
            problems.append(f"videos에 없는 영상 {key!r}")
        if typ not in ("S", "V"):
            problems.append(f"유형은 S/V여야 함 ({typ!r})")
        if not ko:
            problems.append("질의가 비어 있음")
        if not gts or any(b <= a for a, b in gts):
            problems.append(f"정답 구간이 없거나 끝 ≤ 시작 ({gts})")
        src, overlay = item.get("source", "human"), item.get("overlay_text")
        if src not in SOURCES:
            problems.append(f"source는 {'/'.join(SOURCES)} 중 하나 ({src!r})")
        if overlay not in (None, True, False):
            problems.append(f"overlay_text는 true/false ({overlay!r})")
        if problems:
            raise ValueError(f"{path} 질의 #{num}: " + ", ".join(problems))
        seen.add(num)
        queries.append((num, key, typ, ko, gts))
        info[num] = {"source": src, "overlay_text": overlay}
    return QuerySet(_source(path), videos, sorted(queries), info)


def load(path=None, subset=None) -> QuerySet:
    """path가 없으면 queries.py, 있으면 라벨링 JSON. subset(dev/test)을 주면 그 영상의 질의만."""
    qs = _from_module() if path is None else _from_json(Path(path))
    splits = video_splits()
    for num, key, *_ in qs.queries:
        qs.info[num]["split"] = splits.get(qs.videos[key].get("youtube_id"))
    if subset:
        if subset not in SUBSETS:
            raise ValueError(f"subset은 {'/'.join(SUBSETS)} 중 하나 ({subset!r})")
        qs.queries = [q for q in qs.queries if qs.info[q[0]]["split"] == subset]
        if not qs.queries:
            raise ValueError(f"{subset}에 해당하는 질의가 없습니다 ({SPLIT_FILE.name}의 split 열 확인)")
        qs.subset = subset
    return qs
