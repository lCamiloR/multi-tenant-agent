"""
Activity responsável por buscar uma página de contratações da API do PNCP.

No modelo do Temporal, uma Activity é a menor unidade de trabalho com
retry próprio. A decisão de fazer uma Activity por página (e não buscar
todas as páginas em uma só Activity) é estratégica:

- Se a página 7 de 20 falhar, o Temporal reexecuta APENAS ela.
  Com tudo em uma Activity, uma falha na página 7 jogaria fora o trabalho
  das páginas 1–6 e começaria do zero.

- O histórico de execuções no Temporal UI fica granular — você vê
  exatamente qual página falhou e por quê.

- O timeout por Activity pode ser calibrado para uma página (30s),
  não para o fetch completo (minutos).
"""

from datetime import datetime
from temporalio import activity
from src.pipeline.clients.pncp_client import PNCPClient
from src.pipeline.models.state import FetchParams, PageResult

import logging

logger = logging.getLogger(__name__)


@activity.defn(name="fetch_contratacoes_page")
async def fetch_contratacoes_page(params: FetchParams) -> PageResult:
    """
    Busca uma única página de contratações atualizadas no PNCP.

    O decorator @activity.defn registra esta função como uma Activity
    reconhecível pelo worker do Temporal. O parâmetro 'name' é o
    identificador que o Workflow usa para despachar a tarefa — se você
    renomear a função Python, o Workflow continua funcionando desde que
    o 'name' seja mantido.
    """
    client = PNCPClient()

    try:
        # Converte as strings ISO de volta para datetime para o cliente HTTP
        data_inicio = datetime.fromisoformat(params.data_inicio)
        data_fim = datetime.fromisoformat(params.data_fim)

        pagina = await client.get_contratacoes_atualizacao(
            data_inicial=data_inicio,
            data_final=data_fim,
            modalidade=params.modalidade,
            pagina=params.pagina,
            tamanho_pagina=params.tamanho_pagina,
        )

        logger.info(
            f"Página {params.pagina}/{pagina.total_paginas} | "
            f"modalidade={params.modalidade} | "
            f"itens={len(pagina.data)}"
        )

        return PageResult(
            # Serializamos os itens como JSON porque o Temporal precisa
            # serializar o retorno da Activity, e ContratacaoDTO é Pydantic —
            # usamos model_dump_json() para serialização limpa.
            items=[item.model_dump_json(by_alias=False) for item in pagina.data],
            total_paginas=pagina.total_paginas,
            pagina_atual=pagina.numero_pagina,
            empty=pagina.empty or len(pagina.data) == 0,
        )

    finally:
        # Sempre fechamos o cliente HTTP ao fim da Activity para evitar
        # connection leaks — cada Activity tem seu próprio ciclo de vida.
        await client.close()
