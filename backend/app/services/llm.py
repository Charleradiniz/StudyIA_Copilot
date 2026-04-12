import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL

def format_history(history: list[dict] | None) -> str:
    if not history:
        return "Sem histórico anterior."

    lines = []
    for turn in history[-6:]:
        role = "Usuário" if turn.get("role") == "user" else "Assistente"
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines) if lines else "Sem histórico anterior."


def build_prompt(question: str, context: str, history: list[dict] | None = None) -> str:
    return f"""
Você é um assistente especializado em análise de documentos.

Sua tarefa é entender o DOCUMENTO como um todo, não apenas trechos isolados.

REGRAS:
- Considere o histórico da conversa para entender referências curtas como "isso", "o que mais", "explique melhor"
- Identifique os temas principais do documento
- Combine informações de diferentes partes
- NÃO responda apenas listando termos
- NÃO diga "não encontrei informações suficientes" se houver contexto relevante
- Sempre tente inferir o tema central do documento
- Seja claro e objetivo

HISTÓRICO DA CONVERSA:
{format_history(history)}

CONTEXTO DO DOCUMENTO:
{context}

PERGUNTA:
{question}

RESPOSTA:
"""


def generate_answer(question: str, context: str, history: list[dict] | None = None) -> str:
    if not GEMINI_API_KEY:
        return "Google AI Studio API key is not configured."

    prompt = build_prompt(question, context, history)
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    try:
        response = requests.post(
            endpoint,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                },
            },
            timeout=300
        )

        response.raise_for_status()

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            return "The model returned no candidates."

        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if part.get("text"))

        return text.strip() or "The model returned an empty response."

    except requests.exceptions.Timeout:
        return "The model took too long to respond. Please try again."

    except Exception as e:
        return f"Error calling Google AI Studio: {str(e)}"


BASE_INSTRUCTIONS = """
You are a grounded document analysis assistant.
The context is organized by explicit document labels such as [Greek Architecture].

Core rules:
- Answer in the same language used by the user.
- Use the labeled document sections to attribute evidence correctly.
- Synthesize evidence across excerpts instead of treating each excerpt in isolation.
- If the answer requires inference, make a careful inference and make it explicit.
- Prefer the best grounded answer available instead of saying that no information was found when relevant clues exist.
- If the evidence is partial, explain what is supported and what remains uncertain.
- Do not be artificially brief when the context supports a fuller explanation.
- Avoid vague summaries. Include concrete facts, examples, relationships, and patterns from the excerpts.
- If the retrieved excerpts look corrupted, unreadable, symbol-heavy, or mostly made of codes and indexes, say that the extraction quality is insufficient and do not infer the document theme.
""".strip()

COMMON_RESPONSE_REQUIREMENTS = """
Response requirements:
- Give a developed answer, not a one-line summary, unless the user explicitly asked for a very short response.
- When the context is rich, aim for roughly 2 to 5 short paragraphs or a compact structured comparison.
- If enough evidence exists, connect 3 to 5 grounded details instead of stopping after the first point.
- Weave together multiple grounded details from the excerpts instead of repeating generic statements.
- Use the document labels naturally when switching sources or contrasting evidence.
- If several relevant excerpts exist, make use of them instead of relying on only one or two.
- Do not stop after naming a topic. Explain what it means, why it matters, or how the evidence connects.
""".strip()

PROMPT_MODES = {
    "grounded": """
Mode: grounded single-document or focused answer.
- Prioritize the most relevant evidence.
- Explain the main point first, then add the most useful supporting details.
- If the excerpts support nuance, include that nuance instead of stopping at a shallow summary.
""".strip(),
    "multi_document": """
Mode: multi-document synthesis.
- Combine evidence across the labeled documents before answering.
- Explain how the documents connect when the answer depends on more than one source.
- Mention the document labels when switching between sources.
- Build a cohesive synthesis rather than a list of isolated observations.
- Cover the strongest contribution from each relevant document before concluding.
""".strip(),
    "comparison": """
Mode: comparison and cross-document reasoning.
- Compare all relevant labeled documents side by side.
- Highlight similarities, differences, relationships, and important patterns.
- Mention the document labels when presenting each part of the comparison.
- If one document has weaker evidence, provide a partial comparison instead of refusing to answer.
- When possible, compare several grounded points rather than stopping after one or two.
- Start with the overall comparison, then support it with concrete contrasts and overlaps.
""".strip(),
}


def format_history(history: list[dict] | None) -> str:
    if not history:
        return "No prior conversation."

    lines = []
    for turn in history[-6:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines) if lines else "No prior conversation."


def build_mode_instructions(prompt_mode: str) -> str:
    return PROMPT_MODES.get(prompt_mode, PROMPT_MODES["grounded"])


def build_prompt(
    question: str,
    context: str,
    history: list[dict] | None = None,
    prompt_mode: str = "grounded",
) -> str:
    normalized_context = context.strip() or "[No retrieved context]"

    return f"""
{BASE_INSTRUCTIONS}

{COMMON_RESPONSE_REQUIREMENTS}

{build_mode_instructions(prompt_mode)}

Conversation history:
{format_history(history)}

Document context:
{normalized_context}

User question:
{question}

Answer:
"""


def generate_answer(
    question: str,
    context: str,
    history: list[dict] | None = None,
    *,
    prompt_mode: str = "grounded",
) -> str:
    if not GEMINI_API_KEY:
        return "Google AI Studio API key is not configured."

    prompt = build_prompt(question, context, history, prompt_mode=prompt_mode)
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    try:
        response = requests.post(
            endpoint,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.15,
                    "topP": 0.9,
                    "maxOutputTokens": 1400,
                },
            },
            timeout=300,
        )

        response.raise_for_status()

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            return "The model returned no candidates."

        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if part.get("text"))

        return text.strip() or "The model returned an empty response."

    except requests.exceptions.Timeout:
        return "The model took too long to respond. Please try again."

    except Exception as error:
        return f"Error calling Google AI Studio: {str(error)}"


# The runtime overrides below keep the public module API stable while the
# context-aware prompt implementation lives in a clean dedicated module.
from app.services.llm_runtime import *  # noqa: F401,F403,E402


CONTEXT_AWARE_BASE_INSTRUCTIONS = """
You are a grounded document analysis assistant.
The context you receive may already be organized into semantic topics, relationships, comparisons, dependencies, and conflicts.

Core rules:
- Answer in the same language used by the user.
- Treat the structured topic sections as higher-level evidence groups, not as unrelated excerpts.
- Prefer multi-hop reasoning when the answer depends on connecting multiple chunks or documents.
- Explicitly mention important relationships, causal links, dependencies, comparisons, and contradictions when they matter.
- If several chunks support the same point, synthesize them instead of repeating them.
- If the context contains a conflict, explain both sides and state what is well supported versus uncertain.
- Keep traceability in mind: ground the answer in the provided topic sections and chunk evidence.
- If the retrieved excerpts look corrupted, unreadable, symbol-heavy, or mostly made of codes and indexes, say that the extraction quality is insufficient and do not infer the document theme.
""".strip()

CONTEXT_AWARE_RESPONSE_REQUIREMENTS = """
Response requirements:
- Give a developed answer, not a one-line summary, unless the user explicitly asked for a very short response.
- When the context is rich, aim for roughly 2 to 5 short paragraphs or a compact structured comparison.
- Focus on relationships between concepts, not just isolated facts.
- When the context is rich, synthesize the strongest support from the highest-relevance topics before concluding.
- If the context spans multiple documents, explain how they connect.
- If the context highlights dependency, comparison, or conflict, include that structure naturally in the answer.
- If several relevant excerpts exist, make use of them instead of relying on only one or two.
""".strip()

CONTEXT_AWARE_PROMPT_MODES = {
    "grounded": """
Mode: grounded structured answer.
- Start from the most relevant topic cluster.
- Use the strongest supporting evidence first.
- Include the most important relationship if one is present.
""".strip(),
    "multi_document": """
Mode: multi-document synthesis.
- Connect evidence across topic clusters and documents.
- Prefer the clusters that bridge more than one document.
- Explain the shared ideas and then the document-specific nuances.
""".strip(),
    "comparison": """
Mode: comparison and cross-document reasoning.
- Compare the relevant topic clusters side by side.
- Highlight similarities, differences, tensions, and dependencies.
- If the context shows disagreement, explain the conflict explicitly instead of flattening it.
- When possible, compare several grounded points instead of stopping after one or two.
""".strip(),
}


def format_history(history: list[dict] | None) -> str:
    if not history:
        return "No prior conversation."

    lines = []
    for turn in history[-6:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines) if lines else "No prior conversation."


def build_mode_instructions(prompt_mode: str) -> str:
    return CONTEXT_AWARE_PROMPT_MODES.get(prompt_mode, CONTEXT_AWARE_PROMPT_MODES["grounded"])


def build_prompt(
    question: str,
    context: str,
    history: list[dict] | None = None,
    prompt_mode: str = "grounded",
) -> str:
    normalized_context = context.strip() or "[No retrieved context]"

    return f"""
{CONTEXT_AWARE_BASE_INSTRUCTIONS}

{CONTEXT_AWARE_RESPONSE_REQUIREMENTS}

{build_mode_instructions(prompt_mode)}

Conversation history:
{format_history(history)}

Structured context:
{normalized_context}

User question:
{question}

Answer:
"""


def generate_answer(
    question: str,
    context: str,
    history: list[dict] | None = None,
    *,
    prompt_mode: str = "grounded",
) -> str:
    if not GEMINI_API_KEY:
        return "Google AI Studio API key is not configured."

    prompt = build_prompt(question, context, history, prompt_mode=prompt_mode)
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    try:
        response = requests.post(
            endpoint,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.15,
                    "topP": 0.9,
                    "maxOutputTokens": 1400,
                },
            },
            timeout=300,
        )

        response.raise_for_status()

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            return "The model returned no candidates."

        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if part.get("text"))

        return text.strip() or "The model returned an empty response."

    except requests.exceptions.Timeout:
        return "The model took too long to respond. Please try again."

    except Exception as error:
        return f"Error calling Google AI Studio: {str(error)}"
