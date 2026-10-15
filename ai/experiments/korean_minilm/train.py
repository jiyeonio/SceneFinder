"""
SceneFinder Korean MiniLM fine-tuning.

Reproduces the original Korean MiniLM training configuration.

Example:
    python -m ai.experiments.korean_minilm.train \
        --train-jsonl /path/to/minilm_train_pairs_clean.jsonl \
        --output-dir /path/to/new_training_output

Do not upload licensed AI-Hub training data or model weights to GitHub.
"""

import argparse
import json
from pathlib import Path

import torch
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    losses,
)
from sentence_transformers.training_args import (
    SentenceTransformerTrainingArguments,
    BatchSamplers,
)


MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def load_training_pairs(path):
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)

            query = str(record.get("query") or "").strip()
            positive = str(record.get("positive") or "").strip()

            if not query or not positive:
                raise ValueError("Empty query or positive text found.")

            records.append({
                "anchor": query,
                "positive": positive,
            })

    if not records:
        raise ValueError("Training data is empty.")

    return Dataset.from_list(records)


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune SceneFinder Korean MiniLM"
    )

    parser.add_argument(
        "--train-jsonl",
        type=Path,
        required=True
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True
    )

    args = parser.parse_args()

    train_path = args.train_jsonl.resolve()
    output_dir = args.output_dir.resolve()

    if not train_path.is_file():
        raise FileNotFoundError(train_path)

    # 기존 모델과 체크포인트 보호
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists: {output_dir}"
        )

    if output_dir == train_path.parent:
        raise ValueError(
            "Output directory must differ from the data directory."
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "Original training used CUDA with fp16. "
            "Please enable a GPU runtime."
        )

    train_dataset = load_training_pairs(train_path)

    model = SentenceTransformer(
        MODEL_NAME,
        device="cuda"
    )
    model.max_seq_length = 128

    train_loss = losses.MultipleNegativesRankingLoss(
        model=model
    )

    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=1,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        fp16=True,
        bf16=False,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        save_strategy="epoch",
        save_total_limit=1,
        eval_strategy="no",
        logging_steps=100,
        report_to="none",
        seed=42,
        data_seed=42,
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        loss=train_loss,
    )

    print("===== SceneFinder MiniLM Fine-tuning =====")
    print("Training samples:", len(train_dataset))
    print("Model:", MODEL_NAME)
    print("Epochs:", training_args.num_train_epochs)
    print("Batch size:", training_args.per_device_train_batch_size)
    print("Learning rate:", training_args.learning_rate)
    print("Output:", output_dir)

    trainer.train()

    final_dir = output_dir / "final_model"

    if final_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite model: {final_dir}"
        )

    trainer.model.save_pretrained(str(final_dir))

    print("MiniLM fine-tuning completed.")
    print("Saved model:", final_dir)


if __name__ == "__main__":
    main()
