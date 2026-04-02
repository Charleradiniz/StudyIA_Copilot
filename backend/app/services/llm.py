import requests

from app.config import OLLAMA_MODEL, OLLAMA_URL


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
    prompt = build_prompt(question, context)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2  # Slight balance between precision and interpretation
            },
            timeout=300
        )

        response.raise_for_status()

        return response.json()["response"].strip()

    except requests.exceptions.Timeout:
        return "O modelo demorou muito para responder. Tente novamente."

    except Exception as e:
        return f"Erro ao chamar Ollama: {str(e)}"
