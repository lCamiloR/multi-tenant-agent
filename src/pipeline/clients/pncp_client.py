"""
HTTP client for the PNCP public API.

The responsibility of this module is exclusively communication with the external API —
it knows nothing about Temporal, Milvus, or Postgres. This separation is intentional:
if the API changes or we need to switch data sources, only this file changes.

We use httpx instead of requests because it is async-native, which is important
within the Temporal context that runs in an async event loop.
"""

import httpx
from datetime import datetime, timedelta
from logging import getLogger
from src.pipeline.models.pncp import ProcurementsPage

logger = getLogger(__name__)

# Base URL for the PNCP query API
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta"


class PNCPClient:
    """
    Encapsulates all calls to the PNCP API.

    We use an httpx client with a configured timeout to prevent
    a slow API from blocking the Temporal worker indefinitely.
    Temporal has its own Activity-level timeout mechanism,
    but it is good practice to also have a timeout at the HTTP layer.
    """

    def __init__(self, base_url: str = PNCP_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            # The PNCP API is public — no authentication required for queries
        )

    async def get_updated_procurements(
        self,
        start_date: datetime,
        end_date: datetime,
        modality: int,
        page: int = 1,
        page_size: int = 50,
    ) -> ProcurementsPage:
        """
        Fetches procurements updated within a time interval.

        This is the correct endpoint for incremental synchronization — it returns
        only records modified during the period, which is much more efficient
        than fetching everything and comparing locally.

        The date format required by the API is "YYYYMMDD" — that is why
        we convert here, keeping the rest of the code working with datetime.
        """
        fmt = "%Y%m%d"

        params = {
            "dataInicial": start_date.strftime(fmt),
            "dataFinal": end_date.strftime(fmt),
            "codigoModalidadeContratacao": modality,
            "pagina": page,
            "tamanhoPagina": page_size,
        }

        logger.info(
            f"Fetching procurements | modality={modality} "
            f"period={start_date.strftime(fmt)} to {end_date.strftime(fmt)} "
            f"page={page}"
        )

        response = await self.client.get("/v1/contratacoes/atualizacao", params=params)

        # We let httpx raise an exception for status >= 400.
        # Temporal will catch it and apply the RetryPolicy configured in the workflow.
        response.raise_for_status()

        # Status 204 means no data in the period — return an empty page
        if response.status_code == 204:
            return ProcurementsPage(data=[], totalRegistros=0, totalPaginas=0, numeroPagina=page)

        return ProcurementsPage.model_validate(response.json())

    async def close(self):
        await self.client.aclose()
