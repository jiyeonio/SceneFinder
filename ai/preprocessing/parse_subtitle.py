import os
import json
import re
from pathlib import Path


video_id = os.getenv(
    "SCENEFINDER_VIDEO_ID",
    "video_001"
)

subtitle_path = Path(
    os.getenv(
        "SCENEFINDER_SUBTITLE_PATH",
        f"data/processed/{video_id}/subtitle.en-orig.vtt"
    )
)

output_path = Path(
    f"data/processed/{video_id}/subtitle.json"
)


def time_to_seconds(time_str):
    parts = time_str.split(":")

    if len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])

        return hours * 3600 + minutes * 60 + seconds

    elif len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])

        return minutes * 60 + seconds

    return 0


def clean_caption_text(text):
    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", text)

    # 공백 정리
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def remove_overlap(previous_text, current_text):
    """
    이전 자막과 현재 자막이 겹치는 경우,
    현재 자막에서 겹치는 앞부분을 제거한다.

    예:
    previous:
    "welcome to the series where I show you"

    current:
    "welcome to the series where I show you how to cook"

    결과:
    "how to cook"
    """

    previous_words = previous_text.split()
    current_words = current_text.split()

    max_overlap = min(
        len(previous_words),
        len(current_words)
    )

    for overlap_size in range(
        max_overlap,
        0,
        -1
    ):
        if (
            previous_words[-overlap_size:]
            == current_words[:overlap_size]
        ):
            remaining_words = current_words[overlap_size:]

            return " ".join(remaining_words).strip()

    return current_text


# --------------------------------------------------
# VTT 읽기
# --------------------------------------------------

with open(
    subtitle_path,
    "r",
    encoding="utf-8"
) as f:
    lines = f.readlines()


raw_results = []

current_start = None
current_end = None
current_text = []


# --------------------------------------------------
# VTT → 기본 자막 구조
# --------------------------------------------------

for line in lines:

    line = line.strip()

    if "-->" in line:

        if (
            current_start is not None
            and current_text
        ):
            text = clean_caption_text(
                " ".join(current_text)
            )

            if text:
                raw_results.append(
                    {
                        "start_time": round(current_start, 2),
                        "end_time": round(current_end, 2),
                        "text": text
                    }
                )

        current_text = []

        time_parts = line.split("-->")

        start_text = time_parts[0].strip()
        end_text = time_parts[1].strip().split()[0]

        current_start = time_to_seconds(start_text)
        current_end = time_to_seconds(end_text)

    elif (
        line
        and not line.startswith("WEBVTT")
        and not line.startswith("Kind:")
        and not line.startswith("Language:")
    ):

        clean_text = clean_caption_text(line)

        if clean_text:
            current_text.append(clean_text)


# 마지막 자막 추가
if (
    current_start is not None
    and current_text
):
    text = clean_caption_text(
        " ".join(current_text)
    )

    if text:
        raw_results.append(
            {
                "start_time": round(current_start, 2),
                "end_time": round(current_end, 2),
                "text": text
            }
        )


# --------------------------------------------------
# 자동 자막 중복 / 누적 제거
# --------------------------------------------------

results = []

for item in raw_results:

    current_text = item["text"]

    if not results:

        results.append(item)
        continue


    previous_text = results[-1]["text"]

    # 완전히 같은 문장이면 제거
    if current_text == previous_text:
        continue


    cleaned_text = remove_overlap(
        previous_text,
        current_text
    )


    # 겹치는 부분을 제거했더니 빈 문자열이면 제거
    if not cleaned_text:
        continue


    results.append(
        {
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "text": cleaned_text
        }
    )


# --------------------------------------------------
# JSON 저장
# --------------------------------------------------

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


# --------------------------------------------------
# 결과 확인
# --------------------------------------------------

print("=== Subtitle Parsing Result ===")

for item in results[:15]:

    print(
        f"[{item['start_time']:.2f} ~ "
        f"{item['end_time']:.2f}] "
        f"{item['text']}"
    )


print()
print(f"원본 자막 개수: {len(raw_results)}")
print(f"정리 후 자막 개수: {len(results)}")
print(f"저장 위치: {output_path}")