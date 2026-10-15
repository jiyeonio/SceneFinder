"""
SceneFinder Consensus Reranking

V1: 서로 다른 검색 방식의 시간 구간 겹침을 모두 가점
V2: IoU 0.5 이상인 겹침만 가점

실험용 재정렬 알고리즘이며,
정답 구간(Ground Truth)은 순위 결정에 사용하지 않는다.
"""

from ai.features.fusion_search import temporal_iou


def _rank_by_consensus(hybrid, ko, en, min_overlap=0.0):
    groups = {
        "hybrid": hybrid,
        "ko": ko,
        "en": en
    }

    candidates = []

    for source, group in groups.items():
        for rank, candidate in enumerate(group, 1):
            item = dict(candidate)

            item["rank_source"] = source
            item["original_rank"] = rank
            item["rank_score"] = 1.0 / rank

            candidates.append(item)

    for candidate in candidates:
        support = 0.0

        for source, group in groups.items():
            if source == candidate["rank_source"]:
                continue

            best_overlap = max(
                (
                    temporal_iou(candidate, other)
                    for other in group
                ),
                default=0.0
            )

            if best_overlap >= min_overlap:
                support += best_overlap

        candidate["consensus_score"] = (
            candidate["rank_score"] + support
        )

    return sorted(
        candidates,
        key=lambda x: x["consensus_score"],
        reverse=True
    )


def rank_by_consensus(hybrid, ko, en):
    """Consensus V1"""
    return _rank_by_consensus(
        hybrid, ko, en,
        min_overlap=0.0
    )


def rank_by_consensus_v2(hybrid, ko, en):
    """Consensus V2"""
    return _rank_by_consensus(
        hybrid, ko, en,
        min_overlap=0.5
    )
