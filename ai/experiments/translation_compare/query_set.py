"""평가 질의 세트 읽기: queries.py(기본) 또는 라벨링 도구(tools/labeler)가 저장한 JSON.

JSON 형식 (tools/labeler/README.md 참고)
    {
      "format": "scenefinder-labels/1",
      "videos": {"tofu": {"file": "data/raw/korean_test/kr_tofu_001.mp4", "name": "두부", "domain": "요리"}},
      "queries": [{"num": 1, "video": "tofu", "type": "S", "query": "두부를 반으로 자르는 장면", "gt": [[13, 19]]}]
    }
- file: 저장소 루트 기준 상대 경로 또는 절대 경로
- type: S = 말로 설명되는 장면, V = 말로는 안 나오고 화면에만 보이는 장면
- gt: 정답 구간 목록 [[시작초, 끝초], ...] (여러 개면 가장 높은 IoU로 판정)
"""
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCAL_VIDEO_DIR = ROOT / "data/raw/korean_test"
HANDOFF_VIDEO_DIR = ROOT / "ai/experiments/korean_ai_handoff/remaining_176_files/02_Korean_Video_Test"
FORMAT = "scenefinder-labels/1"


class QuerySet:
    def __init__(self, source, videos, queries):
        self.source = source      # 읽은 파일 (결과 meta에 기록)
        self.videos = videos      # 키 → {"file": 경로 문자열, "name": 표시 이름, "handoff": 인수인계 파일명 또는 None}
        self.queries = queries    # [(번호, 영상 키, 유형, 질의, [(시작, 끝), ...])]

    @property
    def video_keys(self):
        """질의가 있는 영상만, 처음 나온 순서대로."""
        return list(dict.fromkeys(key for _, key, _, _, _ in self.queries))

    def name(self, key):
        return self.videos[key].get("name") or key

    def video_path(self, key) -> Path:
        """file이 경로면 그대로(상대 경로는 저장소 루트 기준), 파일명만 있으면 data/raw/korean_test에서,
        없으면 인수인계 폴더(있는 경우)에서 찾습니다. (인수인계 폴더의 한글 파일명은 NFD라 정규화해서 비교)
        테스트 영상은 저장소에 포함하지 않습니다."""
        info = self.videos[key]
        file = Path(info["file"])
        candidates = [file if file.is_absolute() else ROOT / file, LOCAL_VIDEO_DIR / file.name]
        for p in candidates:
            if p.exists():
                return p
        if info.get("handoff"):
            want = unicodedata.normalize("NFC", info["handoff"])
            for p in HANDOFF_VIDEO_DIR.glob("*.mp4"):
                if unicodedata.normalize("NFC", p.name) == want:
                    return p
        raise FileNotFoundError(f"영상을 찾을 수 없습니다 ({key}): {candidates[0]}")


def _from_module():
    import queries as q

    videos = {k: {"file": local, "name": q.VIDEO_NAMES.get(k, k), "handoff": handoff}
              for k, (local, handoff) in q.VIDEO_FILES.items()}
    queries = [(num, key, typ, ko, [tuple(g) for g in gts]) for num, key, typ, ko, gts in q.QUERIES]
    return QuerySet(str(Path(q.__file__).resolve().relative_to(ROOT)), videos, queries)


def _from_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path}: format이 {FORMAT!r}가 아닙니다")
    videos = {k: {"file": v["file"], "name": v.get("name") or k, "handoff": v.get("handoff")}
              for k, v in data["videos"].items()}
    queries, seen = [], set()
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
        if problems:
            raise ValueError(f"{path} 질의 #{num}: " + ", ".join(problems))
        seen.add(num)
        queries.append((num, key, typ, ko, gts))
    try:
        source = str(path.resolve().relative_to(ROOT))
    except ValueError:
        source = str(path.resolve())
    return QuerySet(source, videos, sorted(queries))


def load(path=None) -> QuerySet:
    """path가 없으면 queries.py, 있으면 라벨링 JSON."""
    return _from_module() if path is None else _from_json(Path(path))
