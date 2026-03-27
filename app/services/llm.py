import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"


def generate_answer(question: str, context: str) -> str:
    prompt = f"""
Você é um sistema de EXTRAÇÃO de informações de documentos.

REGRAS IMPORTANTES:
- Responda SOMENTE com a informação encontrada no contexto
- Não explique, não comente, não reformule
- Seja o mais direto possível
- Se a informação não estiver no contexto, responda exatamente:
  "Não encontrei essa informação no contexto"

FOCO DE EXTRAÇÃO:
- Nome → extraia apenas o nome completo
- Email → extraia apenas o email
- Telefone → extraia apenas o número
- Cargo → extraia apenas o cargo/função
- Outras perguntas → responda com o trecho exato mais relevante

CONTEXTO:
{context}

PERGUNTA:
{question}

RESPOSTA:
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1  # 🔥 deixa mais preciso e menos criativo
            },
            timeout=60
        )

        return response.json()["response"].strip()

    except Exception as e:
        return f"Erro ao chamar Ollama: {str(e)}"