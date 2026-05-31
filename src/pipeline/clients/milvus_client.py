"""
Cliente Milvus para operações de embedding e busca semântica.

Este módulo é responsável por toda a interação com o Milvus —
criação de coleções, upsert de vetores e busca por similaridade.

Uma decisão importante de design aqui: separamos o cliente Milvus
do cliente de embeddings (embedder). Isso permite trocar o modelo
de embedding sem afetar a lógica de persistência, e vice-versa.

Para desenvolvimento local, a variável MILVUS_URI pode apontar para
um arquivo .db (Milvus Lite) ou para o servidor standalone em Docker.
"""

import json
from logging import getLogger
from datetime import datetime
from pymilvus import MilvusClient, DataType

logger = getLogger(__name__)

# Nome da coleção no Milvus — equivalente a uma tabela no SQL
COLLECTION_NAME = "licitacoes"

# Dimensão do vetor gerado pelo text-embedding-3-small da OpenAI.
# ATENÇÃO: se trocar o modelo de embedding, este valor deve ser atualizado
# e a coleção precisa ser recriada (vetores de dimensões diferentes são incompatíveis).
EMBEDDING_DIM = 1536


class MilvusLicitacoesClient:
    """
    Abstrai todas as operações Milvus relacionadas a licitações.

    A ideia é que as Activities do Temporal chamem métodos de alto nível
    (upsert, search) sem precisar saber nada sobre schemas ou índices.
    Toda a complexidade do Milvus fica encapsulada aqui.
    """

    def __init__(self, uri: str):
        """
        uri pode ser:
          - "./licitacoes.db"          → Milvus Lite (desenvolvimento local)
          - "http://localhost:19530"   → Milvus standalone (Docker)
          - "https://..."              → Milvus Cloud (produção)
        """
        self.client = MilvusClient(uri=uri)
        self._ensure_collection()

    def _ensure_collection(self):
        """
        Cria a coleção se ela não existir.

        A estratégia 'ensure' (criar só se não existir) é preferível a
        'create or replace' porque preserva dados já indexados entre
        reinicializações do worker. Em produção, mudanças de schema
        devem ser tratadas como migrações explícitas.
        """
        if self.client.has_collection(COLLECTION_NAME):
            logger.info(f"Coleção '{COLLECTION_NAME}' já existe — pulando criação.")
            return

        logger.info(f"Criando coleção '{COLLECTION_NAME}'...")

        # Definimos o schema explicitamente para ter controle sobre
        # quais campos ficam disponíveis como filtros nas buscas.
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)

        # Chave primária — usamos o numeroControlePNCP como ID natural
        # para que o upsert seja idempotente (reprocessar o mesmo item
        # não cria duplicatas).
        schema.add_field("id", DataType.VARCHAR, max_length=100, is_primary=True)

        # O vetor em si — dimensão definida pelo modelo de embedding escolhido
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        # Campos de metadata para filtros híbridos (vetor + filtro estrutural).
        # Exemplo: busca semântica por "desenvolvimento de software" filtrada por uf="SP"
        schema.add_field("uf_sigla", DataType.VARCHAR, max_length=2, default_value="")
        schema.add_field("modalidade_id", DataType.INT64, default_value=0)
        schema.add_field("valor_estimado", DataType.DOUBLE, default_value=0.0)
        schema.add_field("data_encerramento_proposta", DataType.INT64, default_value=0)  # timestamp Unix
        schema.add_field("data_publicacao", DataType.INT64, default_value=0)             # timestamp Unix

        # Índice vetorial — AUTOINDEX deixa o Milvus escolher o melhor algoritmo
        # para o tamanho da coleção. Em produção com milhões de vetores,
        # pode ser substituído por HNSW com parâmetros explícitos.
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type="COSINE",  # Cosine similarity é padrão para embeddings de texto
        )

        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"Coleção '{COLLECTION_NAME}' criada com sucesso.")

    def upsert(self, item_json: str, embedding: list[float]) -> None:
        """
        Insere ou atualiza um registro na coleção.

        O upsert é idempotente pelo 'id' (numeroControlePNCP) —
        se o item já existir, os vetores e metadata são atualizados.
        Isso garante que reprocessamentos do job não causem duplicatas.
        """
        item = json.loads(item_json)

        # Converte datetimes para timestamps Unix inteiros porque
        # o Milvus não tem tipo nativo de datetime — usamos INT64
        # e nas queries comparamos com int(datetime.now().timestamp()).
        encerramento_ts = 0
        if item.get("data_encerramento_proposta"):
            try:
                dt = datetime.fromisoformat(item["data_encerramento_proposta"])
                encerramento_ts = int(dt.timestamp())
            except (ValueError, TypeError):
                pass

        publicacao_ts = 0
        if item.get("data_publicacao_pncp"):
            try:
                dt = datetime.fromisoformat(item["data_publicacao_pncp"])
                publicacao_ts = int(dt.timestamp())
            except (ValueError, TypeError):
                pass

        record = {
            "id": item["numero_controle_pncp"],
            "vector": embedding,
            "uf_sigla": item.get("unidade_orgao", {}).get("uf_sigla", "") or "",
            "modalidade_id": item.get("modalidade_id") or 0,
            "valor_estimado": item.get("valor_total_estimado") or 0.0,
            "data_encerramento_proposta": encerramento_ts,
            "data_publicacao": publicacao_ts,
        }

        self.client.upsert(collection_name=COLLECTION_NAME, data=[record])

    def search(
        self,
        query_vector: list[float],
        uf: str | None = None,
        modalidade_id: int | None = None,
        apenas_abertas: bool = False,
        limit: int = 10,
    ) -> list[dict]:
        """
        Busca semântica com filtros opcionais de metadata.

        Esta é a operação que as Tools do LangGraph vão chamar.
        Os filtros são expressões booleanas na sintaxe do Milvus —
        equivalente ao WHERE do SQL, mas aplicado sobre a metadata
        dos vetores.

        Retorna uma lista de dicts com 'id' (numeroControlePNCP) e
        'distance' (score de similaridade). O agente usa os IDs para
        buscar os dados completos no Postgres via join.
        """
        filtros = []

        if uf:
            filtros.append(f'uf_sigla == "{uf}"')

        if modalidade_id:
            filtros.append(f"modalidade_id == {modalidade_id}")

        if apenas_abertas:
            agora_ts = int(datetime.now().timestamp())
            filtros.append(f"data_encerramento_proposta > {agora_ts}")

        filtro_str = " && ".join(filtros) if filtros else ""

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            filter=filtro_str,
            limit=limit,
            output_fields=["id", "uf_sigla", "modalidade_id", "data_encerramento_proposta"],
        )

        # results é uma lista de listas (uma por query vector)
        # como sempre passamos um único vetor, pegamos results[0]
        return [
            {
                "id": hit["entity"]["id"],
                "score": hit["distance"],
                "uf_sigla": hit["entity"].get("uf_sigla"),
                "modalidade_id": hit["entity"].get("modalidade_id"),
            }
            for hit in results[0]
        ]

    def close(self):
        self.client.close()
