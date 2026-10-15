"""
SceneFinder Korean MiniLM full-validation retrieval evaluation.

Reproduces the original notebook's summary-to-transcript
retrieval metrics: Recall@1, Recall@5, and MRR.

The transcript at the same index is treated as
the single correct answer.

This does NOT measure temporal video moment retrieval.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer, util


BASE_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def load_validation_pairs(path):
    pairs = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)

            query = record.get("query")
            positive = record.get("positive")

            if not query or not positive:
                raise ValueError("Empty evaluation text found.")

            pairs.append({
                "query": query,
                "positive": positive
            })

    if not pairs:
        raise ValueError("Validation dataset is empty.")

    return pairs


def evaluate_minilm(model, queries, documents):
    """Match the original notebook's retrieval evaluation."""

    query_embeddings = model.encode(
        queries,
        convert_to_tensor=True,
        show_progress_bar=False
    )

    doc_embeddings = model.encode(
        documents,
        convert_to_tensor=True,
        show_progress_bar=False
    )

    scores = util.cos_sim(
        query_embeddings,
        doc_embeddings
    )

    ranks = []

    for i in range(len(queries)):
        ranked_indices = (
            scores[i].argsort(descending=True).tolist()
        )

        ranks.append(ranked_indices.index(i) + 1)

    return {
        "recall_at_1": float(
            np.mean([r == 1 for r in ranks])
        ),
        "recall_at_5": float(
            np.mean([r <= 5 for r in ranks])
        ),
        "mrr": float(
            np.mean([1 / r for r in ranks])
        )
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Korean MiniLM retrieval"
    )

    parser.add_argument(
        "--val-jsonl",
        type=Path,
        required=True
    )

    parser.add_argument(
        "--finetuned-model",
        type=Path,
        required=True
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True
    )

    args = parser.parse_args()

    val_path = args.val_jsonl.resolve()
    model_path = args.finetuned_model.resolve()
    output_path = args.output.resolve()

    if not val_path.is_file():
        raise FileNotFoundError(val_path)

    if not model_path.is_dir():
        raise FileNotFoundError(model_path)

    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite: {output_path}"
        )

    pairs = load_validation_pairs(val_path)

    queries = [p["query"] for p in pairs]
    documents = [p["positive"] for p in pairs]

    print("===== SceneFinder Korean MiniLM evaluation =====")
    print("Validation pairs:", len(pairs))

    print("\n[Original MiniLM]")
    original_model = SentenceTransformer(BASE_MODEL)

    original_result = evaluate_minilm(
        original_model, queries, documents
    )

    print(original_result)

    print("\n[Fine-tuned MiniLM]")
    trained_model = SentenceTransformer(
        str(model_path)
    )

    trained_result = evaluate_minilm(
        trained_model, queries, documents
    )

    print(trained_result)

    result = {
        "evaluation": (
            "AI-Hub full validation "
            "summary-to-transcript retrieval"
        ),
        "sample_size": len(pairs),
        "original": original_result,
        "finetuned": trained_result
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open("x", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n✅ Evaluation completed!")
    print("Saved:", output_path)


if __name__ == "__main__":
    main()
