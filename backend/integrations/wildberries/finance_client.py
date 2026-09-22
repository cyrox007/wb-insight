from typing import Any

from integrations.wildberries import endpoints
from integrations.wildberries.client import WBClient
from settings import config


class WBFinanceClient(WBClient):
    """Актуальные методы финансового API Wildberries для сверки расчётов."""

    @staticmethod
    def _endpoint_interval(endpoint: str) -> float:
        if endpoint in {"finance.sales_reports_list", "finance.balance"}:
            return config.WB_FINANCE_MIN_INTERVAL_SECONDS
        return WBClient._endpoint_interval(endpoint)

    async def get_sales_reports_list(self, payload: dict[str, Any]):
        request_body = dict(payload)
        request_body.setdefault("limit", 1000)
        request_body.setdefault("offset", 0)
        request_body.setdefault("period", "weekly")
        return await self._request(
            "POST",
            endpoints.FINANCE_REPORTS_LIST,
            endpoint="finance.sales_reports_list",
            json_data=request_body,
        )

    async def get_balance(self):
        return await self._request(
            "GET",
            endpoints.FINANCE_BALANCE,
            endpoint="finance.balance",
        )
