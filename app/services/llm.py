import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"


def build_prompt(question: str, context: str) -> str:
    return f"""
Você é um assistente inteligente que responde perguntas com base em documentos.

REGRAS:
- Responda de forma clara, objetiva e natural
- Você PODE interpretar e resumir o conteúdo
- NÃO precisa copiar exatamente o texto
- Use apenas informações do contexto
- Se a resposta não estiver clara, diga que não encontrou
- Responda com segurança, sem usar expressões como "parece" ou "provavelmente"

CASOS ESPECIAIS (extração direta):
- Nome → retorne apenas o nome completo
- Email → retorne apenas o email
- Telefone → retorne apenas o número
- Cargo → retorne apenas o cargo

CONTEXTO:
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
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2  # 🔥 leve equilíbrio entre precisão e interpretação
            },
            timeout=300
        )

        response.raise_for_status()

        return response.json()["response"].strip()

    except requests.exceptions.Timeout:
        return "O modelo demorou muito para responder. Tente novamente."

    except Exception as e:
        return f"Erro ao chamar Ollama: {str(e)}"