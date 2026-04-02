import requests

from app.config import GEMINI_API_KEY, GEMINI_MODEL


def build_prompt(question: str, context: str) -> str:
    return f"""
Você é um assistente especializado em análise de documentos.

Sua tarefa é entender o DOCUMENTO como um todo, não apenas trechos isolados.

REGRAS:
- Identifique os temas principais do documento
- Combine informações de diferentes partes
- NÃO responda apenas listando termos
- NÃO diga "não encontrei informações suficientes" se houver contexto relevante
- Sempre tente inferir o tema central do documento
- Seja claro e objetivo

CONTEXTO DO DOCUMENTO:
{context}

PERGUNTA:
{question}

RESPOSTA:
"""


def generate_answer(question: str, context: str) -> str:
    if not GEMINI_API_KEY:
        return "Google AI Studio API key is not configured."

    prompt = build_prompt(question, context)
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
