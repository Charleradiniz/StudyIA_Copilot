from functools import lru_cache
import re
import unicodedata


STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no",
    "na", "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com",
    "sem", "sobre", "que", "se", "ao", "aos", "ou", "como", "mais", "menos",
    "muito", "muita", "muitos", "muitas", "ser", "estar", "fala", "falar",
    "documento", "esse", "essa", "isso", "ele", "ela",
}
SUMMARY_HINTS = {
    "resuma", "resumo", "sumario", "sobre", "arquivo", "curriculo", "perfil",
    "geral", "visao", "overview", "describe",
}
FOLLOW_UP_HINTS = {
    "mais", "melhor", "detalhe", "detalhes", "isso", "essa", "esse", "aquilo",
    "tambem", "aprofunde", "continue", "continua", "complementa", "explique",
    "explica", "fale", "fala",
}
COMPARISON_HINTS = {
    "compare", "comparar", "comparacao", "comparativo", "comparison",
    "comparisons", "similar", "similarity", "similarities", "difference",
    "differences", "different", "differs", "distinguish", "contrast",
    "contraste", "contrastar", "versus", "vs", "relacao", "relationship",
    "relationships", "between", "ambos", "ambas", "common", "comum",
}
COMPARISON_PHRASES = (
    "side by side",
    "em comum",
    "lado a lado",
    "quais as diferencas",
    "quais as semelhancas",
    "how do",
    "what is the relationship",
)
TEXT_TOKEN_PATTERN = re.compile(r"\S+")
CODE_LIKE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9&<>'|./:=+_-]{2,}$")
MIN_USABLE_CONTEXT_QUALITY = 0.34
LOW_QUALITY_ANSWER = (
    "Nao consegui responder com seguranca porque o texto extraido deste PDF "
    "parece estar muito ruidoso, corrompido ou pouco legivel. "
    "Tente uma versao com texto selecionavel ou aplique OCR antes do upload."
)


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(character for character in normalized if not unicodedata.combining(character))


def normalize_hint_text(text: str) -> str:
    return strip_accents((text or "").lower()).strip()


def extract_hint_tokens(text: str) -> list[str]:
    return re.findall(r"\w+", normalize_hint_text(text))


def rewrite_query(question: str) -> str:
    return question.strip() if question else ""


def tokenize(text: str) -> list[str]:
    if not text:
        return []

    tokens = re.findall(r"\w+", normalize_hint_text(text))
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def is_summary_query(question: str) -> bool:
    return any(token in SUMMARY_HINTS for token in extract_hint_tokens(question))


def is_follow_up_question(question: str) -> bool:
    raw_tokens = extract_hint_tokens(question)
    if len(raw_tokens) <= 4:
        return True
    return any(token in FOLLOW_UP_HINTS for token in raw_tokens)


def is_comparison_query(question: str) -> bool:
    lowered_question = normalize_hint_text(question)
    raw_tokens = extract_hint_tokens(lowered_question)

    if any(token in COMPARISON_HINTS for token in raw_tokens):
        return True

    return any(normalize_hint_text(phrase) in lowered_question for phrase in COMPARISON_PHRASES)


def detect_prompt_mode(question: str, document_count: int) -> str:
    if document_count <= 1:
        return "grounded"

    if is_comparison_query(question):
        return "comparison"

    return "multi_document"


def build_effective_query(question: str, history: list[dict] | None = None) -> str:
    if not history or not is_follow_up_question(question):
        return question

    last_user = ""
    last_assistant = ""

    for turn in reversed(history):
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant" and not last_assistant:
            last_assistant = content[:500]
            continue

        if role == "user":
            last_user = content[:200]
            break

    contextual_parts = [part for part in [last_user, last_assistant, question] if part]
    return " ".join(contextual_parts)


@lru_cache(maxsize=16384)
def analyze_text_quality_cached(text: str) -> tuple[float, float, float, float, float, bool]:
    normalized = (text or "").strip()
    if not normalized:
        return (0.0, 0.0, 0.0, 1.0, 1.0, True)

    tokens = TEXT_TOKEN_PATTERN.findall(normalized)
    total_chars = max(len(normalized), 1)
    alpha_ratio = sum(1 for character in normalized if character.isalpha()) / total_chars
    strong_symbol_ratio = (
        sum(
            1
            for character in normalized
            if not character.isalnum()
            and not character.isspace()
            and character not in ".,;:?!()/%-"
        )
        / total_chars
    )

    natural_tokens = []
    code_like_tokens = []

    for token in tokens:
        letters_only = "".join(character for character in token if character.isalpha())
        if len(letters_only) >= 3:
            natural_tokens.append(token)

        if not CODE_LIKE_TOKEN_PATTERN.fullmatch(token):
            continue

        if token.isdigit() or len(letters_only) >= 3:
            continue

        code_like_tokens.append(token)

    token_count = max(len(tokens), 1)
    natural_token_ratio = len(natural_tokens) / token_count
    code_like_ratio = len(code_like_tokens) / token_count
    alpha_component = min(alpha_ratio / 0.55, 1.0)
    symbol_component = max(0.0, 1.0 - min(strong_symbol_ratio / 0.12, 1.0))
    code_component = max(0.0, 1.0 - min(code_like_ratio / 0.45, 1.0))
    quality_score = round(
        (alpha_component * 0.4)
        + (natural_token_ratio * 0.4)
        + (symbol_component * 0.1)
        + (code_component * 0.1),
        4,
    )
    is_low_quality = (
        len(normalized) >= 60
        and quality_score < MIN_USABLE_CONTEXT_QUALITY
        and (
            natural_token_ratio < 0.33
            or code_like_ratio > 0.35
            or alpha_ratio < 0.42
        )
    )

    return (
        quality_score,
        alpha_ratio,
        natural_token_ratio,
        code_like_ratio,
        strong_symbol_ratio,
        is_low_quality,
    )


def analyze_text_quality(text: str) -> dict:
    (
        quality_score,
        alpha_ratio,
        natural_token_ratio,
        code_like_ratio,
        strong_symbol_ratio,
        is_low_quality,
    ) = analyze_text_quality_cached((text or "").strip())

    return {
        "quality_score": quality_score,
        "alpha_ratio": alpha_ratio,
        "natural_token_ratio": natural_token_ratio,
        "code_like_ratio": code_like_ratio,
        "strong_symbol_ratio": strong_symbol_ratio,
        "is_low_quality": is_low_quality,
    }


def is_low_quality_chunk(chunk: dict) -> bool:
    return analyze_text_quality(chunk.get("text") or "").get("is_low_quality", True)


def build_low_quality_response(question: str) -> dict:
    return {
        "question": question,
        "answer": LOW_QUALITY_ANSWER,
        "sources": [],
    }
