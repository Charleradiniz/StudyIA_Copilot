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
""".strip()

PROMPT_MODES = {
    "grounded": """
Mode: grounded single-document or focused answer.
- Prioritize the most relevant evidence.
- Keep the answer direct and grounded in the provided excerpts.
""".strip(),
    "multi_document": """
Mode: multi-document synthesis.
- Combine evidence across the labeled documents before answering.
- Explain how the documents connect when the answer depends on more than one source.
- Mention the document labels when switching between sources.
""".strip(),
    "comparison": """
Mode: comparison and cross-document reasoning.
- Compare all relevant labeled documents side by side.
- Highlight similarities, differences, relationships, and important patterns.
- Mention the document labels when presenting each part of the comparison.
- If one document has weaker evidence, provide a partial comparison instead of refusing to answer.
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
