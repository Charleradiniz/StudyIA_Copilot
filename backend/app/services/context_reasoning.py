from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from statistics import mean
from typing import Any, Callable
import math
import re

import networkx as nx
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


Chunk = dict[str, Any]
Retriever = Callable[[list[dict], str, str, str], list[Chunk]]

_TOKEN_PATTERN = re.compile(r"\b[\wÀ-ÿ][\wÀ-ÿ\-]{2,}\b", re.UNICODE)
_PROPER_NOUN_PATTERN = re.compile(
    r"(?:[A-ZÀ-Ý][\wÀ-ÿ\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ\-]+){0,2})",
    re.UNICODE,
)
_COMPARISON_MARKERS = (
    "compared to",
    "compared with",
    "in contrast",
    "whereas",
    "while",
    "unlike",
    "versus",
    "vs",
    "comparison",
    "comparar",
    "comparação",
    "comparacao",
    "por outro lado",
)
_CAUSE_EFFECT_MARKERS = (
    "because",
    "causes",
    "caused by",
    "leads to",
    "results in",
    "drives",
    "therefore",
    "thus",
    "due to",
    "provoca",
    "leva a",
    "resulta em",
    "por causa",
)
_DEPENDENCY_MARKERS = (
    "depends on",
    "dependent on",
    "requires",
    "relies on",
    "based on",
    "prerequisite",
    "depende de",
    "requer",
    "necessita",
    "baseado em",
)
_CONFLICT_MARKERS = (
    "however",
    "but",
    "although",
    "nevertheless",
    "on the other hand",
    "despite",
    "porém",
    "porem",
    "mas",
    "contudo",
    "entretanto",
)
_NEGATION_MARKERS = (
    "not",
    "no",
    "never",
    "without",
    "cannot",
    "isn't",
    "aren't",
    "não",
    "nao",
    "sem",
    "nunca",
)
_RELATIONAL_QUERY_HINTS = (
    "compare",
    "comparison",
    "contrast",
    "difference",
    "relationship",
    "between",
    "relacao",
    "relação",
    "como",
    "how do",
    "how does",
)
_TOPIC_STOPWORDS = {
    "about",
    "after",
    "also",
    "been",
    "between",
    "both",
    "cada",
    "como",
    "com",
    "data",
    "depois",
    "document",
    "documento",
    "from",
    "have",
    "into",
    "mais",
    "menos",
    "mesmo",
    "muito",
    "muita",
    "para",
    "porque",
    "sobre",
    "their",
    "them",
    "there",
    "these",
    "those",
    "through",
    "very",
    "which",
    "with",
    "without",
    "your",
    "a",
    "an",
    "and",
    "ao",
    "as",
    "at",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "for",
    "in",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "of",
    "on",
    "por",
    "que",
    "the",
    "to",
    "uma",
    "um",
}
_EMBEDDING_CACHE: OrderedDict[str, np.ndarray] = OrderedDict()
_EMBEDDING_CACHE_MAXSIZE = 4096


def _normalize_entity(entity: str) -> str:
    return re.sub(r"\s+", " ", (entity or "").strip().lower())


def _display_term(term: str) -> str:
    normalized = (term or "").strip()
    if not normalized:
        return normalized
    return normalized if any(char.isupper() for char in normalized) else normalized.title()


def _extract_chunk_keywords(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_PATTERN.findall(text or "")
        if token.lower() not in _TOPIC_STOPWORDS
    }


def _set_overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(min(len(left), len(right)), 1)


def _is_relational_query(query: str) -> bool:
    lowered_query = (query or "").lower()
    return any(marker in lowered_query for marker in _RELATIONAL_QUERY_HINTS)


def _contains_marker(text: str, marker: str) -> bool:
    lowered_text = (text or "").lower()
    lowered_marker = marker.lower()
    if " " in lowered_marker or "'" in lowered_marker:
        return lowered_marker in lowered_text
    return re.search(rf"(?<!\w){re.escape(lowered_marker)}(?!\w)", lowered_text) is not None


def _chunk_signature(chunk: Chunk) -> tuple:
    return (
        chunk.get("doc_id"),
        chunk.get("chunk_id") if chunk.get("chunk_id") is not None else chunk.get("id"),
        chunk.get("page"),
        (chunk.get("text") or "").strip(),
    )


def _chunk_position(chunk: Chunk, default: int) -> int:
    for key in ("reasoning_position", "_reasoning_position", "retrieval_rank", "id"):
        value = chunk.get(key)
        if isinstance(value, int):
            return value
    return default


def _chunk_trace(chunk: Chunk) -> str:
    doc_label = chunk.get("doc_label") or chunk.get("doc_name") or chunk.get("doc_id") or "Document"
    page = chunk.get("page")
    page_label = f"page {page + 1}" if isinstance(page, int) else "page ?"
    chunk_id = chunk.get("chunk_id") if chunk.get("chunk_id") is not None else chunk.get("id")
    return f"{doc_label} | {page_label} | chunk {chunk_id}"


def _normalize_chunk(chunk: Chunk, position: int) -> Chunk:
    normalized = dict(chunk)
    normalized["text"] = (chunk.get("text") or "").strip()
    normalized["reasoning_position"] = _chunk_position(chunk, position)
    normalized["query_score"] = float(chunk.get("score") or 0.0)
    normalized["trace"] = _chunk_trace(normalized)
    return normalized


def _is_low_signal_chunk(chunk: Chunk) -> bool:
    text = (chunk.get("text") or "").strip()
    if not text:
        return True

    tokens = _TOKEN_PATTERN.findall(text)
    if len(tokens) < 7:
        return True

    alpha_chars = sum(1 for char in text if char.isalpha())
    symbol_chars = sum(1 for char in text if not char.isalnum() and not char.isspace() and char not in ".,;:?!()-/%")
    if alpha_chars / max(len(text), 1) < 0.35:
        return True
    if symbol_chars / max(len(text), 1) > 0.16:
        return True

    return False


def _chunk_information_score(chunk: Chunk) -> float:
    text = (chunk.get("text") or "").strip()
    token_count = len(_TOKEN_PATTERN.findall(text))
    punctuation_bonus = 0.08 if any(marker in text for marker in ".!?;:") else 0.0
    length_bonus = min(len(text) / 600, 1.0) * 0.18
    token_bonus = min(token_count / 70, 1.0) * 0.12
    query_score = max(float(chunk.get("query_score") or 0.0), 0.0)
    return round(query_score * 0.55 + length_bonus + token_bonus + punctuation_bonus, 4)


def _cache_embedding(text: str, vector: np.ndarray) -> None:
    _EMBEDDING_CACHE[text] = vector
    _EMBEDDING_CACHE.move_to_end(text)
    while len(_EMBEDDING_CACHE) > _EMBEDDING_CACHE_MAXSIZE:
        _EMBEDDING_CACHE.popitem(last=False)


def _encode_texts(texts: list[str], semantic_model=None) -> tuple[np.ndarray, str]:
    if semantic_model is not None:
        ordered_vectors: list[np.ndarray | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_positions: list[int] = []

        for index, text in enumerate(texts):
            cached = _EMBEDDING_CACHE.get(text)
            if cached is None:
                missing_texts.append(text)
                missing_positions.append(index)
                continue

            ordered_vectors[index] = cached
            _EMBEDDING_CACHE.move_to_end(text)

        if missing_texts:
            encoded = np.asarray(
                semantic_model.encode(missing_texts, normalize_embeddings=True),
                dtype=np.float32,
            )
            for local_index, text in enumerate(missing_texts):
                vector = encoded[local_index]
                _cache_embedding(text, vector)
                ordered_vectors[missing_positions[local_index]] = vector

        return np.vstack(ordered_vectors).astype(np.float32), "semantic"

    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=4096)
    matrix = tfidf.fit_transform(texts)
    return matrix.toarray().astype(np.float32), "tfidf"


def _top_similarity_pairs(similarity_matrix: np.ndarray, limit: int = 24) -> list[tuple[int, int, float]]:
    pairs: list[tuple[int, int, float]] = []
    size = similarity_matrix.shape[0]
    for left in range(size):
        for right in range(left + 1, size):
            pairs.append((left, right, float(similarity_matrix[left, right])))
    pairs.sort(key=lambda item: item[2], reverse=True)
    return pairs[:limit]


def retrieve_chunks(
    question: str,
    docs: list[dict],
    *,
    effective_question: str,
    prompt_mode: str,
    retriever: Retriever,
    limit: int = 18,
) -> dict[str, Any]:
    all_results = retriever(docs, question, effective_question, prompt_mode)
    candidate_chunks = [
        _normalize_chunk(chunk, position)
        for position, chunk in enumerate(all_results[:limit])
        if (chunk.get("text") or "").strip()
    ]
    return {
        "question": question,
        "effective_question": effective_question,
        "all_results": all_results,
        "candidate_chunks": candidate_chunks,
    }


def compute_chunk_similarity(
    chunks: list[Chunk],
    *,
    semantic_model=None,
    cross_encoder=None,
    max_chunks: int = 18,
    refine_top_edges: int = 12,
) -> dict[str, Any]:
    selected_chunks = [_normalize_chunk(chunk, index) for index, chunk in enumerate(chunks[:max_chunks])]
    if not selected_chunks:
        return {
            "chunks": [],
            "similarity_matrix": np.zeros((0, 0), dtype=np.float32),
            "similarity_edges": [],
            "backend": "none",
        }

    if len(selected_chunks) == 1:
        return {
            "chunks": selected_chunks,
            "similarity_matrix": np.eye(1, dtype=np.float32),
            "similarity_edges": [],
            "backend": "single",
        }

    texts = [chunk["text"] for chunk in selected_chunks]
    vectors, backend = _encode_texts(texts, semantic_model=semantic_model)
    similarity_matrix = cosine_similarity(vectors).astype(np.float32)
    np.fill_diagonal(similarity_matrix, 1.0)

    keyword_sets = [_extract_chunk_keywords(text) for text in texts]
    entity_sets = [
        {_normalize_entity(entity) for entity in _extract_chunk_entities(text)}
        for text in texts
    ]
    for left in range(len(selected_chunks)):
        for right in range(left + 1, len(selected_chunks)):
            keyword_overlap = _set_overlap_score(keyword_sets[left], keyword_sets[right])
            entity_overlap = _set_overlap_score(entity_sets[left], entity_sets[right])
            shared_entity_count = len(entity_sets[left] & entity_sets[right])
            lexical_boost = (
                (keyword_overlap * 0.35)
                + (entity_overlap * 0.25)
                + min(shared_entity_count, 3) * 0.06
            )
            blended_similarity = max(
                float(similarity_matrix[left, right]),
                min(
                    1.0,
                    (float(similarity_matrix[left, right]) * 0.72) + lexical_boost,
                ),
            )
            similarity_matrix[left, right] = blended_similarity
            similarity_matrix[right, left] = blended_similarity

    if cross_encoder is not None:
        candidate_pairs = [
            (left, right, score)
            for left, right, score in _top_similarity_pairs(similarity_matrix, limit=refine_top_edges * 2)
            if score >= 0.45
        ][:refine_top_edges]
        if candidate_pairs:
            pair_inputs = [(texts[left], texts[right]) for left, right, _ in candidate_pairs]
            refined_scores = cross_encoder.predict(pair_inputs)
            for (left, right, original_score), refined_score in zip(candidate_pairs, refined_scores):
                refined_similarity = 1.0 / (1.0 + math.exp(-float(refined_score)))
                blended_score = float((original_score * 0.65) + (refined_similarity * 0.35))
                similarity_matrix[left, right] = blended_score
                similarity_matrix[right, left] = blended_score
            backend = f"{backend}+cross-encoder"

    similarity_edges = [
        {
            "left": left,
            "right": right,
            "score": round(score, 4),
            "left_trace": selected_chunks[left]["trace"],
            "right_trace": selected_chunks[right]["trace"],
        }
        for left, right, score in _top_similarity_pairs(similarity_matrix)
        if score >= 0.3
    ]

    return {
        "chunks": selected_chunks,
        "similarity_matrix": similarity_matrix,
        "similarity_edges": similarity_edges,
        "backend": backend,
    }


def remove_redundant_chunks(
    chunks: list[Chunk],
    similarity_matrix: np.ndarray,
    *,
    duplicate_threshold: float = 0.92,
) -> dict[str, Any]:
    if not chunks:
        return {
            "chunks": [],
            "keep_indices": [],
            "removed_duplicates": [],
            "similarity_matrix": similarity_matrix,
            "redundancy_score": 0.0,
        }

    keep_indices: list[int] = []
    removed_duplicates: list[dict[str, Any]] = []
    ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: (
            _chunk_information_score(chunks[index]),
            -_chunk_position(chunks[index], index),
        ),
        reverse=True,
    )

    for index in ranked_indices:
        chunk = chunks[index]
        if _is_low_signal_chunk(chunk):
            removed_duplicates.append({
                "index": index,
                "reason": "low_signal",
                "trace": chunk["trace"],
            })
            continue

        duplicate_of = next(
            (
                kept_index
                for kept_index in keep_indices
                if similarity_matrix[index, kept_index] >= duplicate_threshold
            ),
            None,
        )
        if duplicate_of is not None:
            removed_duplicates.append({
                "index": index,
                "reason": "near_duplicate",
                "trace": chunk["trace"],
                "duplicate_of": chunks[duplicate_of]["trace"],
                "score": round(float(similarity_matrix[index, duplicate_of]), 4),
            })
            continue

        keep_indices.append(index)

    if not keep_indices:
        keep_indices = [max(range(len(chunks)), key=lambda index: _chunk_information_score(chunks[index]))]

    keep_indices.sort(key=lambda index: _chunk_position(chunks[index], index))
    reduced_matrix = similarity_matrix[np.ix_(keep_indices, keep_indices)]
    redundancy_score = round(1.0 - (len(keep_indices) / max(len(chunks), 1)), 4)

    return {
        "chunks": [chunks[index] for index in keep_indices],
        "keep_indices": keep_indices,
        "removed_duplicates": removed_duplicates,
        "similarity_matrix": reduced_matrix,
        "redundancy_score": redundancy_score,
    }


def _cluster_cohesion(similarity_matrix: np.ndarray) -> float:
    if similarity_matrix.size == 0 or similarity_matrix.shape[0] <= 1:
        return 1.0

    values = [
        float(similarity_matrix[left, right])
        for left in range(similarity_matrix.shape[0])
        for right in range(left + 1, similarity_matrix.shape[0])
    ]
    return round(mean(values), 4) if values else 1.0


def _extract_chunk_entities(text: str) -> list[str]:
    proper_nouns = [match.group(0).strip() for match in _PROPER_NOUN_PATTERN.finditer(text)]
    normalized_tokens = [
        token.lower()
        for token in _TOKEN_PATTERN.findall(text)
        if token.lower() not in _TOPIC_STOPWORDS
    ]

    ranked_entities: list[str] = []
    seen_entities: set[str] = set()
    for entity in proper_nouns:
        normalized_entity = _normalize_entity(entity)
        if normalized_entity in seen_entities:
            continue
        seen_entities.add(normalized_entity)
        ranked_entities.append(entity)

    for token, _ in Counter(normalized_tokens).most_common(6):
        normalized_entity = _normalize_entity(token)
        if normalized_entity in seen_entities:
            continue
        seen_entities.add(normalized_entity)
        ranked_entities.append(token)

    return ranked_entities[:8]


def _extract_cluster_topic(cluster_chunks: list[Chunk]) -> tuple[str, list[str]]:
    token_counter: Counter[str] = Counter()
    entity_counter: Counter[str] = Counter()
    entity_labels: dict[str, str] = {}

    for chunk in cluster_chunks:
        text = chunk.get("text") or ""
        token_counter.update(
            token.lower()
            for token in _TOKEN_PATTERN.findall(text)
            if token.lower() not in _TOPIC_STOPWORDS
        )
        for entity in _extract_chunk_entities(text):
            normalized_entity = _normalize_entity(entity)
            entity_labels.setdefault(normalized_entity, entity)
            entity_counter[normalized_entity] += 1

    shared_entity_keys = [entity for entity, count in entity_counter.items() if count >= 2]
    if not shared_entity_keys:
        shared_entity_keys = [entity for entity, _ in entity_counter.most_common(4)]

    shared_entities = [
        _display_term(entity_labels.get(entity, entity))
        for entity in shared_entity_keys[:6]
    ]

    if shared_entities:
        topic_label = " / ".join(shared_entities[:3])
    else:
        topic_label = " / ".join(token.title() for token, _ in token_counter.most_common(3)) or "Related Evidence"

    return topic_label, shared_entities[:6]


def _detect_relation_types(text_left: str, text_right: str, shared_entities: set[str]) -> list[str]:
    combined = f"{text_left} {text_right}".lower()
    relation_types: list[str] = []

    if any(_contains_marker(combined, marker) for marker in _CAUSE_EFFECT_MARKERS):
        relation_types.append("cause-effect")
    if any(_contains_marker(combined, marker) for marker in _DEPENDENCY_MARKERS):
        relation_types.append("dependency")
    if any(_contains_marker(combined, marker) for marker in _COMPARISON_MARKERS):
        relation_types.append("comparison")

    has_conflict_marker = any(_contains_marker(combined, marker) for marker in _CONFLICT_MARKERS)
    negation_mismatch = (
        any(_contains_marker(text_left, marker) for marker in _NEGATION_MARKERS)
        != any(_contains_marker(text_right, marker) for marker in _NEGATION_MARKERS)
    )
    if shared_entities and (has_conflict_marker or negation_mismatch):
        relation_types.append("conflict")

    if shared_entities and not relation_types:
        relation_types.append("support")

    return relation_types


def cluster_chunks(
    chunks: list[Chunk],
    similarity_matrix: np.ndarray,
    *,
    query: str,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    if len(chunks) == 1:
        topic_label, shared_entities = _extract_cluster_topic(chunks)
        return [{
            "cluster_id": 0,
            "topic_label": topic_label,
            "shared_entities": shared_entities,
            "chunks": chunks,
            "cohesion": 1.0,
            "chunk_count": 1,
            "doc_count": len({chunk.get("doc_id") for chunk in chunks}),
            "query_score": round(float(chunks[0].get("query_score") or 0.0), 4),
            "sort_index": _chunk_position(chunks[0], 0),
            "rank_score": round(float(chunks[0].get("query_score") or 0.0), 4),
        }]

    distance_matrix = np.clip(1.0 - similarity_matrix, 0.0, 1.0)
    # Retrieval already narrows the pool, so a looser threshold keeps related
    # evidence grouped instead of fragmenting every supporting chunk.
    distance_threshold = 0.67 if len(chunks) <= 8 else 0.62

    try:
        clustering = AgglomerativeClustering(
            metric="precomputed",
            linkage="average",
            distance_threshold=distance_threshold,
            n_clusters=None,
        )
    except TypeError:
        clustering = AgglomerativeClustering(
            affinity="precomputed",
            linkage="average",
            distance_threshold=distance_threshold,
            n_clusters=None,
        )

    labels = clustering.fit_predict(distance_matrix)
    grouped_indices: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        grouped_indices[int(label)].append(index)

    clusters: list[dict[str, Any]] = []
    for cluster_id, indices in sorted(
        grouped_indices.items(),
        key=lambda item: min(_chunk_position(chunks[index], index) for index in item[1]),
    ):
        cluster_chunks_sorted = sorted(
            (chunks[index] for index in indices),
            key=lambda chunk: _chunk_position(chunk, 0),
        )
        cluster_matrix = similarity_matrix[np.ix_(indices, indices)]
        topic_label, shared_entities = _extract_cluster_topic(cluster_chunks_sorted)
        query_score = round(mean(float(chunk.get("query_score") or 0.0) for chunk in cluster_chunks_sorted), 4)
        cohesion = _cluster_cohesion(cluster_matrix)
        doc_count = len({chunk.get("doc_id") for chunk in cluster_chunks_sorted if chunk.get("doc_id")})
        support_score = min(len(cluster_chunks_sorted) / 4, 1.0)
        doc_diversity_score = min(doc_count / 2, 1.0)
        multi_doc_bonus = 0.08 if doc_count > 1 else 0.0
        rank_score = round(
            (query_score * 0.45)
            + (cohesion * 0.2)
            + (support_score * 0.15)
            + (doc_diversity_score * 0.12)
            + multi_doc_bonus,
            4,
        )
        if "compare" in query.lower() or "relationship" in query.lower() or "relacao" in query.lower():
            rank_score = round(rank_score + (0.06 if doc_count > 1 else 0.0), 4)

        clusters.append({
            "cluster_id": cluster_id,
            "topic_label": topic_label,
            "shared_entities": shared_entities,
            "chunks": cluster_chunks_sorted,
            "cohesion": cohesion,
            "chunk_count": len(cluster_chunks_sorted),
            "doc_count": doc_count,
            "query_score": query_score,
            "sort_index": min(_chunk_position(chunk, 0) for chunk in cluster_chunks_sorted),
            "rank_score": rank_score,
        })

    clusters.sort(key=lambda cluster: (-cluster["rank_score"], cluster["sort_index"]))
    for cluster_index, cluster in enumerate(clusters, start=1):
        cluster["topic_index"] = cluster_index
    return clusters


def extract_relationships(
    clusters: list[dict[str, Any]],
    *,
    query: str,
) -> dict[str, Any]:
    graph = nx.Graph()
    cross_cluster_links: list[dict[str, Any]] = []
    relational_query = _is_relational_query(query)

    for cluster in clusters:
        relationships: list[dict[str, Any]] = []
        chunk_entities: list[set[str]] = []
        cluster_keywords: set[str] = set()
        entity_labels: dict[str, str] = {}

        for chunk in cluster["chunks"]:
            cluster_keywords.update(_extract_chunk_keywords(chunk.get("text") or ""))
            entities = {_normalize_entity(entity) for entity in _extract_chunk_entities(chunk.get("text") or "")}
            chunk_entities.append(entities)
            for entity in entities:
                graph.add_node(entity)
                entity_labels.setdefault(entity, _display_term(entity))

        for left in range(len(cluster["chunks"])):
            for right in range(left + 1, len(cluster["chunks"])):
                shared_entities = chunk_entities[left] & chunk_entities[right]
                relation_types = _detect_relation_types(
                    cluster["chunks"][left].get("text") or "",
                    cluster["chunks"][right].get("text") or "",
                    shared_entities,
                )
                if not relation_types:
                    continue

                entities = [
                    entity_labels.get(entity, _display_term(entity))
                    for entity in sorted(shared_entities)[:3]
                ] or cluster.get("shared_entities", [])[:3]
                relation = {
                    "types": relation_types,
                    "entities": entities,
                    "left_trace": cluster["chunks"][left]["trace"],
                    "right_trace": cluster["chunks"][right]["trace"],
                }
                relationships.append(relation)

                for entity in entities:
                    for other in entities:
                        if entity == other:
                            continue
                        graph.add_edge(entity, other, relation="/".join(relation_types))

        deduped_relationships: list[dict[str, Any]] = []
        seen_relation_keys = set()
        for relation in relationships:
            relation_key = (tuple(relation["types"]), tuple(relation["entities"]))
            if relation_key in seen_relation_keys:
                continue
            seen_relation_keys.add(relation_key)
            deduped_relationships.append(relation)

        cluster["relationships"] = deduped_relationships[:5]
        cluster["conflict_count"] = sum(
            1 for relation in deduped_relationships if "conflict" in relation["types"]
        )
        cluster["relation_count"] = len(deduped_relationships)
        cluster["cross_topic_relationships"] = []
        cluster["_entity_keys"] = set(entity_labels)
        cluster["_entity_labels"] = entity_labels
        cluster["_keyword_set"] = cluster_keywords
        cluster["_representative_text"] = " ".join(
            (chunk.get("text") or "").strip()
            for chunk in cluster["chunks"][:2]
        )
        cluster["rank_score"] = round(
            cluster["rank_score"] + min(cluster["relation_count"], 3) * 0.03 + cluster["conflict_count"] * 0.02,
            4,
        )

    for left in range(len(clusters)):
        for right in range(left + 1, len(clusters)):
            shared_entity_keys = clusters[left].get("_entity_keys", set()) & clusters[right].get("_entity_keys", set())
            shared_keywords = clusters[left].get("_keyword_set", set()) & clusters[right].get("_keyword_set", set())
            shared_terms = [
                clusters[left].get("_entity_labels", {}).get(entity, _display_term(entity))
                for entity in sorted(shared_entity_keys)[:3]
            ]
            if not shared_terms:
                shared_terms = [_display_term(term) for term in sorted(shared_keywords)[:3]]
            if not shared_terms:
                continue

            relation_types = _detect_relation_types(
                clusters[left].get("_representative_text", ""),
                clusters[right].get("_representative_text", ""),
                set(shared_terms),
            )
            if not relation_types and shared_terms:
                relation_types = ["support"]
            if not relation_types and relational_query:
                relation_types = ["comparison"]
            if not relation_types:
                continue

            link = {
                "from_cluster_id": clusters[left]["cluster_id"],
                "to_cluster_id": clusters[right]["cluster_id"],
                "from": clusters[left]["topic_index"],
                "to": clusters[right]["topic_index"],
                "entities": shared_terms,
                "types": relation_types,
            }
            cross_cluster_links.append(link)
            clusters[left]["cross_topic_relationships"].append(link)
            clusters[right]["cross_topic_relationships"].append(link)
            clusters[left]["rank_score"] = round(clusters[left]["rank_score"] + 0.02, 4)
            clusters[right]["rank_score"] = round(clusters[right]["rank_score"] + 0.02, 4)

    clusters.sort(key=lambda cluster: (-cluster["rank_score"], cluster["sort_index"]))
    topic_index_by_cluster_id = {}
    for cluster_index, cluster in enumerate(clusters, start=1):
        cluster["topic_index"] = cluster_index
        topic_index_by_cluster_id[cluster["cluster_id"]] = cluster_index

    for link in cross_cluster_links:
        link["from"] = topic_index_by_cluster_id.get(link["from_cluster_id"], link["from"])
        link["to"] = topic_index_by_cluster_id.get(link["to_cluster_id"], link["to"])

    for cluster in clusters:
        for link in cluster.get("cross_topic_relationships", []):
            link["from"] = topic_index_by_cluster_id.get(link["from_cluster_id"], link["from"])
            link["to"] = topic_index_by_cluster_id.get(link["to_cluster_id"], link["to"])

    return {
        "clusters": clusters,
        "cluster_graph": graph,
        "cluster_links": cross_cluster_links[:6],
    }


def build_structured_context(
    clusters: list[dict[str, Any]],
    *,
    max_clusters: int = 4,
    max_chunks_per_cluster: int = 4,
) -> str:
    sections: list[str] = []

    for cluster in clusters[:max_clusters]:
        lines = [f"[Topic {cluster['topic_index']}: {cluster['topic_label']}]"]
        doc_labels = []
        for chunk in cluster["chunks"]:
            doc_label = chunk.get("doc_label") or chunk.get("doc_name") or chunk.get("doc_id")
            if doc_label and doc_label not in doc_labels:
                doc_labels.append(doc_label)
        lines.append(
            "Coverage: "
            f"{cluster['chunk_count']} chunks across {cluster['doc_count']} documents | "
            f"relevance {cluster['rank_score']:.2f} | cohesion {cluster['cohesion']:.2f}"
        )
        if doc_labels:
            lines.append(f"Documents: {', '.join(doc_labels)}")
        if cluster.get("shared_entities"):
            lines.append(f"Shared entities: {', '.join(cluster['shared_entities'][:6])}")

        for relation in cluster.get("relationships", [])[:4]:
            if "conflict" in relation["types"]:
                prefix = "Conflict"
            elif "cause-effect" in relation["types"]:
                prefix = "Relationship"
            elif "dependency" in relation["types"]:
                prefix = "Dependency"
            elif "comparison" in relation["types"]:
                prefix = "Comparison"
            else:
                prefix = "Relationship"

            relation_detail = ", ".join(relation["entities"]) if relation["entities"] else "linked evidence"
            lines.append(
                f"{prefix}: {relation_detail} "
                f"({relation['left_trace']} <> {relation['right_trace']})"
            )

        for excerpt_index, chunk in enumerate(cluster["chunks"][:max_chunks_per_cluster], start=1):
            lines.append(f"Chunk {excerpt_index} [{chunk['trace']}]")
            lines.append(chunk["text"])

        sections.append("\n".join(lines))

    cross_topic_lines: list[str] = []
    seen_link_keys = set()
    for cluster in clusters[:max_clusters]:
        for link in cluster.get("cross_topic_relationships", []):
            link_key = (
                min(link["from"], link["to"]),
                max(link["from"], link["to"]),
                tuple(link.get("types", [])),
                tuple(link.get("entities", [])),
            )
            if link_key in seen_link_keys:
                continue
            seen_link_keys.add(link_key)

            if "conflict" in link["types"]:
                prefix = "Conflict"
            elif "cause-effect" in link["types"]:
                prefix = "Relationship"
            elif "dependency" in link["types"]:
                prefix = "Dependency"
            elif "comparison" in link["types"]:
                prefix = "Comparison"
            else:
                prefix = "Relationship"

            relation_detail = ", ".join(link["entities"]) if link.get("entities") else "linked evidence"
            left_topic, right_topic = sorted((link["from"], link["to"]))
            cross_topic_lines.append(
                f"{prefix}: {relation_detail} (Topic {left_topic} <> Topic {right_topic})"
            )

    if cross_topic_lines:
        sections.append("[Cross-topic relationships]\n" + "\n".join(cross_topic_lines[:6]))

    return "\n\n".join(sections)


def run_context_aware_reasoning(
    question: str,
    chunks: list[Chunk],
    *,
    semantic_model=None,
    cross_encoder=None,
    desired_source_count: int = 5,
    desired_context_count: int = 8,
    max_reasoning_chunks: int = 18,
) -> dict[str, Any]:
    similarity_result = compute_chunk_similarity(
        chunks,
        semantic_model=semantic_model,
        cross_encoder=cross_encoder,
        max_chunks=max_reasoning_chunks,
    )
    reasoning_chunks = similarity_result["chunks"]
    similarity_matrix = similarity_result["similarity_matrix"]

    deduped = remove_redundant_chunks(reasoning_chunks, similarity_matrix)
    deduped_chunks = deduped["chunks"]
    deduped_matrix = deduped["similarity_matrix"]

    clusters = cluster_chunks(deduped_chunks, deduped_matrix, query=question)
    relationship_result = extract_relationships(clusters, query=question)
    ranked_clusters = relationship_result["clusters"]
    structured_context = build_structured_context(
        ranked_clusters,
        max_clusters=min(4, max(len(ranked_clusters), 1)),
        max_chunks_per_cluster=min(4, max(desired_context_count, 1)),
    )

    context_chunks: list[Chunk] = []
    source_chunks: list[Chunk] = []
    seen_signatures = set()

    for cluster in ranked_clusters:
        for chunk in cluster["chunks"]:
            signature = _chunk_signature(chunk)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            context_chunks.append(chunk)
            if len(context_chunks) >= desired_context_count:
                break
        if len(context_chunks) >= desired_context_count:
            break

    seen_signatures.clear()
    for cluster in ranked_clusters:
        for chunk in cluster["chunks"]:
            signature = _chunk_signature(chunk)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            source_chunks.append(chunk)
            if len(source_chunks) >= desired_source_count:
                break
        if len(source_chunks) >= desired_source_count:
            break

    metrics = {
        "cluster_count": len(ranked_clusters),
        "context_chunk_count": len(context_chunks),
        "source_chunk_count": len(source_chunks),
        "cross_topic_link_count": len(relationship_result["cluster_links"]),
        "redundancy_score": deduped["redundancy_score"],
        "avg_cluster_cohesion": round(
            mean(cluster["cohesion"] for cluster in ranked_clusters),
            4,
        ) if ranked_clusters else 0.0,
        "multi_doc_cluster_count": sum(1 for cluster in ranked_clusters if cluster["doc_count"] > 1),
        "similarity_backend": similarity_result["backend"],
    }

    return {
        "structured_context": structured_context,
        "clusters": ranked_clusters,
        "context_chunks": context_chunks,
        "source_chunks": source_chunks,
        "similarity_edges": similarity_result["similarity_edges"],
        "removed_duplicates": deduped["removed_duplicates"],
        "cluster_links": relationship_result["cluster_links"],
        "metrics": metrics,
    }
