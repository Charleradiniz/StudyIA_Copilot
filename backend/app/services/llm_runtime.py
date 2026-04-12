import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL

BASE_INSTRUCTIONS = """
You are a grounded document analysis assistant.
The context may be organized into semantic topics, document groups, relationships, comparisons, dependencies, and conflicts.

Core rules:
- Answer in the same language used by the user.
- Treat each topic section as a coherent evidence group instead of isolated excerpts.
- Prefer multi-hop reasoning when the answer depends on connecting multiple chunks or documents.
- Explicitly mention important relationships, causal links, dependencies, comparisons, and contradictions when they matter.
- If several chunks support the same point, synthesize them instead of repeating them.
- If the context contains a conflict, explain both sides and state what is well supported versus uncertain.
- Keep traceability in mind: ground the answer in the provided topic sections and chunk evidence.
- If the retrieved excerpts look corrupted, unreadable, symbol-heavy, or mostly made of codes and indexes, say that the extraction quality is insufficient and do not infer the document theme.
""".strip()

COMMON_RESPONSE_REQUIREMENTS = """
Response requirements:
- Give a developed answer, not a one-line summary, unless the user explicitly asked for a very short response.
- When the context is rich, aim for roughly 2 to 5 short paragraphs or a compact structured comparison.
- Focus on relationships between concepts, not just isolated facts.
- When the context is rich, synthesize the strongest support from the highest-relevance topics before concluding.
- If the context spans multiple documents, explain how they connect.
- If the context highlights dependency, comparison, or conflict, include that structure naturally in the answer.
- If several relevant excerpts exist, make use of them instead of relying on only one or two.
""".strip()

PROMPT_MODES = {
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
