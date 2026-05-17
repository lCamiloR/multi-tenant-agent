"""
Cliente HTTP para a API pública do PNCP.

A responsabilidade deste módulo é exclusivamente a comunicação com a API externa —
ele não sabe nada sobre Temporal, Milvus ou Postgres. Essa separação é intencional:
se a API mudar ou precisarmos trocar de fonte de dados, apenas este arquivo muda.

Usamos httpx em vez de requests porque é async-native, o que é importante
dentro do contexto do Temporal que roda em event loop assíncrono.
"""

import httpx
from datetime import datetime, timedelta
from logging import getLogger
from src.pipeline.models.pncp import PaginaContratacoes, ContratacaoDTO

logger = getLogger(__name__)

# Base URL da API de consulta do PNCP
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta"


class PNCPClient:
    """
    Encapsula todas as chamadas à API do PNCP.

    Usamos um client httpx com timeout configurado para evitar que
    uma API lenta bloqueie o worker do Temporal indefinidamente.
    O Temporal tem seu próprio mecanismo de timeout por Activity,
    mas é boa prática ter um timeout também na camada HTTP.
    """

    def __init__(self, base_url: str = PNCP_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            # A API do PNCP é pública — sem autenticação necessária para consulta
        )

    async def get_contratacoes_atualizacao(
        self,
        data_inicial: datetime,
        data_final: datetime,
        modalidade: int,
        pagina: int = 1,
        tamanho_pagina: int = 50,
    ) -> PaginaContratacoes:
        """
        Busca contratações atualizadas em um intervalo de tempo.

        Este é o endpoint correto para sincronização incremental — ele retorna
        apenas registros que foram modificados no período, o que é muito mais
        eficiente do que buscar tudo e comparar localmente.

        O formato de data exigido pela API é "YYYYMMDDHHmmss" — por isso
        fazemos a conversão aqui, mantendo o resto do código trabalhando com datetime.
        """
        fmt = "%Y%m%d%H%M%S"

        params = {
            "dataInicial": data_inicial.strftime(fmt),
            "dataFinal": data_final.strftime(fmt),
            "codigoModalidadeContratacao": modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina,
        }

        logger.info(
            f"Buscando contratações | modalidade={modalidade} "
            f"período={data_inicial.strftime(fmt)} até {data_final.strftime(fmt)} "
            f"página={pagina}"
        )

        response = await self.client.get("/v1/contratacoes/atualizacao", params=params)

        # Deixamos o httpx lançar exceção para status >= 400.
        # O Temporal vai capturar e aplicar a RetryPolicy configurada no workflow.
        response.raise_for_status()

        # Status 204 significa que não há dados no período — retornamos página vazia
        if response.status_code == 204:
            return PaginaContratacoes(data=[], totalRegistros=0, totalPaginas=0, numeroPagina=pagina)

        return PaginaContratacoes.model_validate(response.json())

    async def close(self):
        await self.client.aclose()
