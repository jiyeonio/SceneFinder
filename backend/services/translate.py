"""검색어 한국어 → 영어 번역 (Moment-DETR/CLIP은 영어 검색어가 필요합니다).

로컬 모델을 쓰므로 API 키가 필요 없습니다. 처음 한 번은 모델을 내려받습니다.
- 기본: facebook/nllb-200-distilled-600M (약 2.4GB)
- .env에 TRANSLATE_MODEL=Helsinki-NLP/opus-mt-ko-en 로 바꾸면 가벼운 모델(약 300MB)을 씁니다.
번역에 실패하면 원문을 그대로 돌려줍니다.
"""
import logging
import os
import re
import threading

logger = logging.getLogger("uvicorn.error")

MODEL_NAME = os.getenv("TRANSLATE_MODEL", "facebook/nllb-200-distilled-600M")
IS_NLLB = "nllb" in MODEL_NAME.lower()
HANGUL_RE = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

# 모델이 잘 못 옮기는 외래어/이름은 번역 전에 영어로 먼저 바꿉니다. (필요하면 자유롭게 추가)
GLOSSARY = {
    "페널티킥": "penalty kick",
    "프리킥": "free kick",
    "코너킥": "corner kick",
    "골키퍼": "goalkeeper",
    "세리머니": "celebration",
    "어시스트": "assist",
    "드리블": "dribbling",
    "슈팅": "shot",
    "헤딩": "header",
    "손흥민": "Son Heung-min",
    "쯔양": "Tzuyang",
}
_GLOSSARY_KEYS = sorted(GLOSSARY, key=len, reverse=True)  # 긴 단어부터 바꿉니다

# 모델 로딩은 한 번에 하나만 합니다. (서버 시작 직후 워밍업과 첫 검색이 동시에 로딩하면
# "Cannot copy out of meta tensor" 오류가 날 수 있습니다.)
_LOAD_LOCK = threading.Lock()
_model_cache = None
_translations: dict[str, str] = {}  # 성공한 번역만 저장합니다 (실패는 저장하지 않음)


def _apply_glossary(text: str) -> str:
    for k in _GLOSSARY_KEYS:
        if k in text:
            text = text.replace(k, f" {GLOSSARY[k]} ")
    return re.sub(r"\s+", " ", text).strip()


def _load():
    global _model_cache
    with _LOAD_LOCK:
        if _model_cache is None:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            if IS_NLLB:
                tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang="kor_Hang")
            else:
                tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            try:
                model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
                model.to("cpu")  # meta 텐서가 남아 있으면 여기서 바로 오류가 납니다
            except Exception as e:
                logger.warning("번역 모델 기본 로딩 실패, 다른 방식으로 다시 시도합니다: %s", e)
                model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, low_cpu_mem_usage=False)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device).eval()
            _model_cache = (tokenizer, model, device)
        return _model_cache


def to_english(query: str) -> str:
    q = query.strip()
    if not q or not HANGUL_RE.search(q):
        return q  # 이미 영어(한글 없음)면 그대로
    if q in _translations:
        return _translations[q]

    try:
        import torch

        tokenizer, model, device = _load()
        src = _apply_glossary(q)
        if not HANGUL_RE.search(src):
            text = src  # 사전만으로 전부 영어가 됐으면 번역 모델이 필요 없음
        else:
            batch = tokenizer(
                [src], return_tensors="pt", padding=True, truncation=True, max_length=128
            ).to(device)
            gen_kwargs = {"max_length": 64, "num_beams": 4}
            if IS_NLLB:
                gen_kwargs["forced_bos_token_id"] = tokenizer.convert_tokens_to_ids("eng_Latn")
            with torch.no_grad():
                out = model.generate(**batch, **gen_kwargs)
            text = tokenizer.decode(out[0], skip_special_tokens=True).strip()
        if text:
            if len(_translations) > 256:
                _translations.clear()
            _translations[q] = text
            return text
        return q
    except Exception as e:
        logger.warning("검색어 번역 실패, 원문을 사용합니다: %s", e)
        return q