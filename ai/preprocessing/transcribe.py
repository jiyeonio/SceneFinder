import json
from pathlib import Path

from faster_whisper import WhisperModel


audio_path = "data/processed/video_001/audio.wav"
output_path = Path("data/processed/video_001/transcript.json")

# 처음 테스트는 CPU에서도 부담이 덜한 small 모델 사용
model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

print("STT 시작...")

segments, info = model.transcribe(
    audio_path,
    beam_size=5
)

results = []

for segment in segments:
    item = {
        "start_time": round(segment.start, 2),
        "end_time": round(segment.end, 2),
        "text": segment.text.strip()
    }

    results.append(item)

    print(
        f"[{item['start_time']:.2f} ~ {item['end_time']:.2f}] "
        f"{item['text']}"
    )


with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        results,
        f,
        ensure_ascii=False,
        indent=2
    )


print()
print("STT 완료!")
print(f"감지 언어: {info.language}")
print(f"저장 위치: {output_path}")