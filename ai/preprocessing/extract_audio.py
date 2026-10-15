import subprocess
from pathlib import Path

video_path = "data/raw/test_audio.mp4"

output_dir = Path("data/processed/video_001")
output_dir.mkdir(parents=True, exist_ok=True)

audio_path = output_dir / "audio.wav"

command = [
    "ffmpeg",
    "-y",
    "-i", video_path,
    "-vn",
    "-acodec", "pcm_s16le",
    "-ar", "16000",
    "-ac", "1",
    str(audio_path)
]

print("오디오 추출 시작...")

result = subprocess.run(
    command,
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("오디오 추출 완료!")
    print(f"저장 위치: {audio_path}")
else:
    print("오디오 추출 실패")
    print(result.stderr)