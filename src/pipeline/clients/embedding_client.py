"""
Embedding generation client.

We isolate embedding generation in its own module for an important reason:
the embedding model is a dependency that can change.
If tomorrow you want to swap text-embedding-3-small for an open-source model
running locally (e.g.: multilingual-e5 via HuggingFace),
only this file needs to change — Activities and Milvus don't know
which model generated the vector.

The only contract that matters is: text goes in, list of floats comes out.
"""

from logging import getLogger
from openai import AsyncOpenAI

logger = getLogger(__name__)

# Chosen embedding model.
# text-embedding-3-small is the ideal balance between cost and quality for Portuguese text.
# Generates vectors of 1536 dimensions — must match EMBEDDING_DIM in milvus_client.py.
EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingClient:
    """
    Wrapper over the OpenAI embeddings API.

    We use AsyncOpenAI because Temporal Activities run in an async context.
    Synchronous calls inside an event loop would block the entire worker —
    causing timeouts and performance degradation.
    """

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        """
        Generates an embedding vector for the provided text.

        The text is the `embedding_text` field of ProcurementDTO —
        a concatenation of procurement_object with additional_information.
        This field concentrates the richest semantic content of the procurement.
        """
        # The API accepts empty strings but returns vectors without semantic meaning.
        # Better to fail explicitly than to index noise.
        if not text or not text.strip():
            raise ValueError("Text for embedding cannot be empty.")

        logger.debug(f"Generating embedding for text of {len(text)} characters.")

        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text.strip(),
        )

        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for multiple texts in a single API call.

        Using batch is significantly more efficient than calling
        embed() in a loop — it reduces network latency and cost per token.
        Useful for initial synchronizations (bulk load) where there are many
        items to index at once.
        """
        if not texts:
            return []

        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[t.strip() for t in texts if t.strip()],
        )

        return [item.embedding for item in response.data]
