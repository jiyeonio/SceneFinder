"""
SceneFinder Korean MiniLM training data preparation.

Input:
    AI-Hub TL_12 and VL_12 TAR files containing ZIP archives of JSON labels.

Output:
    minilm_train_pairs.jsonl
    minilm_train_pairs_clean.jsonl
    minilm_val_pairs.jsonl

AI-Hub source data and generated text pairs must not be committed to GitHub.
"""

import argparse
import io
import json
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

from sentence_transformers import SentenceTransformer


MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

MAX_TOKENS = 128
EXCLUDED_VAL_IDS = {"MYL_18127", "MYL_18128"}


def load_archive(tar_path):
    """Read the single ZIP archive stored inside an AI-Hub TAR file."""

    with tarfile.open(tar_path, "r:*") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]

        if len(members) != 1:
            raise ValueError(
                f"Expected one ZIP in {tar_path}, found {len(members)}"
            )

        extracted = tar.extractfile(members[0])

        if extracted is None:
            raise ValueError(f"Cannot read TAR member: {tar_path}")

        zip_bytes = extracted.read()

    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))

    if archive.testzip() is not None:
        archive.close()
        raise ValueError(f"Damaged ZIP archive: {tar_path}")

    return archive


def build_pairs(archive, tokenizer, split):
    """Create summary-to-transcript pairs with the original token filter."""

    pairs = []

    for name in archive.namelist():
        if not name.lower().endswith(".json"):
            continue

        data = json.loads(archive.read(name).decode("utf-8-sig"))

        video_id = data.get("metadata", {}).get("filename")

        if split == "val" and video_id in EXCLUDED_VAL_IDS:
            continue

        summary = str(data.get("summary") or "").strip()

        terms = data.get("video", {}).get("term", [])

        transcript = " ".join(
            str(term.get("transcription") or "").strip()
            for term in terms
            if isinstance(term, dict)
        ).strip()

        if not summary or not transcript:
            continue

        summary_tokens = len(
            tokenizer(
                summary,
                truncation=False,
                verbose=False
            )["input_ids"]
        )

        transcript_tokens = len(
            tokenizer(
                transcript,
                truncation=False,
                verbose=False
            )["input_ids"]
        )

        if (
            summary_tokens > MAX_TOKENS
            or transcript_tokens > MAX_TOKENS
        ):
            continue

        pairs.append({
            "video_id": video_id,
            "query": summary,
            "positive": transcript
        })

    return pairs


def save_jsonl(path, records):
    """Create a new JSONL file without overwriting existing data."""

    with path.open("x", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--train-tar", type=Path, required=True)
    parser.add_argument("--val-tar", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args()

    train_tar = args.train_tar.resolve()
    val_tar = args.val_tar.resolve()

    if not train_tar.is_file() or not val_tar.is_file():
        raise FileNotFoundError("Training or Validation TAR not found.")

    if train_tar == val_tar:
        raise ValueError("Training and Validation TAR must differ.")

    if not train_tar.name.startswith("TL_12"):
        raise ValueError("Expected a TL_12 Training TAR file.")

    if not val_tar.name.startswith("VL_12"):
        raise ValueError("Expected a VL_12 Validation TAR file.")

    output_dir = args.output_dir.resolve()

    output_files = {
        "train": output_dir / "minilm_train_pairs.jsonl",
        "clean": output_dir / "minilm_train_pairs_clean.jsonl",
        "val": output_dir / "minilm_val_pairs.jsonl"
    }

    for path in output_files.values():
        if path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing file: {path}"
            )

    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = MAX_TOKENS
    tokenizer = model.tokenizer

    with load_archive(train_tar) as train_archive:
        train_pairs = build_pairs(
            train_archive, tokenizer, split="train"
        )

    with load_archive(val_tar) as val_archive:
        val_pairs = build_pairs(
            val_archive, tokenizer, split="val"
        )

    train_ids = {p["video_id"] for p in train_pairs}
    val_ids = {p["video_id"] for p in val_pairs}

    overlap = train_ids & val_ids

    if overlap:
        raise ValueError(
            f"Training/Validation video ID overlap: {len(overlap)}"
        )

    query_counts = Counter(
        p["query"].strip() for p in train_pairs
    )

    clean_pairs = [
        p for p in train_pairs
        if query_counts[p["query"].strip()] == 1
    ]

    if not train_pairs or not clean_pairs or not val_pairs:
        raise ValueError("One or more datasets are empty.")

    output_dir.mkdir(parents=True, exist_ok=True)

    save_jsonl(output_files["train"], train_pairs)
    save_jsonl(output_files["clean"], clean_pairs)
    save_jsonl(output_files["val"], val_pairs)

    print("===== SceneFinder MiniLM data preparation =====")
    print("Training pairs:", len(train_pairs))
    print("Clean training pairs:", len(clean_pairs))
    print("Validation pairs:", len(val_pairs))
    print("Training/Validation ID overlap:", len(overlap))
    print("Output:", output_dir)


if __name__ == "__main__":
    main()
