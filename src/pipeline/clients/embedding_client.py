"""
Cliente de geração de embeddings.

Isolamos a geração de embeddings em seu próprio módulo por uma razão
importante: o modelo de embedding é uma dependência que pode mudar.
Se amanhã você quiser trocar o text-embedding-3-small por um modelo
open-source rodando localmente (ex: multilingual-e5 via HuggingFace),
apenas este arquivo precisa mudar — as Activities e o Milvus não sabem
qual modelo gerou o vetor.

O único contrato que importa é: entra texto, sai lista de floats.
"""

from logging import getLogger
from openai import AsyncOpenAI

logger = getLogger(__name__)

# Modelo de embedding escolhido.
# text-embedding-3-small é o ponto ideal entre custo e qualidade para português.
# Gera vetores de 1536 dimensões — deve corresponder ao EMBEDDING_DIM no milvus_client.py.
EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingClient:
    """
    Wrapper sobre a API de embeddings da OpenAI.

    Usamos AsyncOpenAI porque as Activities do Temporal rodam em contexto
    assíncrono. Chamadas síncronas dentro de um event loop bloqueariam
    o worker inteiro — o que causaria timeouts e degradação de performance.
    """

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        """
        Gera um vetor de embedding para o texto fornecido.

        O texto é o campo `texto_para_embedding` do ContratacaoDTO —
        uma concatenação do objetoCompra com informacaoComplementar.
        Esse campo concentra o conteúdo semântico mais rico da licitação.
        """
        # A API aceita strings vazias mas retorna vetores sem significado semântico.
        # Melhor falhar explicitamente do que indexar ruído.
        if not text or not text.strip():
            raise ValueError("Texto para embedding não pode ser vazio.")

        logger.debug(f"Gerando embedding para texto de {len(text)} caracteres.")

        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text.strip(),
        )

        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Gera embeddings para múltiplos textos em uma única chamada à API.

        Usar batch é significativamente mais eficiente do que chamar
        embed() em loop — reduz latência de rede e custo por token.
        Útil para sincronizações iniciais (bulk load) onde há muitos
        itens para indexar de uma vez.
        """
        if not texts:
            return []

        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[t.strip() for t in texts if t.strip()],
        )

        return [item.embedding for item in response.data]
