import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class BioTimeClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        auth_type: str = "jwt",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.auth_type = auth_type
        self.timeout = timeout
        self._token: str | None = None

    def authenticate(self) -> str:
        if self.auth_type == "jwt":
            endpoint = "/jwt-api-token-auth/"
        else:
            endpoint = "/api-token-auth/"

        logger.info("Authenticating to BioTime at %s", self.base_url)
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json={"username": self.username, "password": self.password},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        token = data.get("token")

        if not token:
            raise RuntimeError(f"BioTime token not found in response: {data}")

        self._token = token
        logger.info("BioTime authentication successful")
        return token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self.authenticate()

        prefix = "JWT" if self.auth_type == "jwt" else "Token"
        return {
            "Content-Type": "application/json",
            "Authorization": f"{prefix} {self._token}",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(
            url,
            headers=self._headers(),
            params=params or {},
            timeout=self.timeout,
        )

        if response.status_code in (401, 403):
            logger.warning("BioTime token expired, re-authenticating")
            self.authenticate()
            response = requests.get(
                url,
                headers=self._headers(),
                params=params or {},
                timeout=self.timeout,
            )

        response.raise_for_status()
        return response.json()

    def get_devices(self, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._get("/iclock/api/terminals/", params={"page": page, "page_size": page_size})

    def get_employees(
        self,
        page: int = 1,
        page_size: int = 100,
        emp_code: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if emp_code:
            params["emp_code"] = emp_code
        return self._get("/personnel/api/employees/", params=params)

    def get_departments(self, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._get("/personnel/api/departments/", params={"page": page, "page_size": page_size})

    def get_transactions(
        self,
        start_time: str,
        end_time: str,
        page: int = 1,
        page_size: int = 1000,
        emp_code: str | None = None,
        terminal_sn: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "start_time": start_time,
            "end_time": end_time,
            "page": page,
            "page_size": page_size,
        }
        if emp_code:
            params["emp_code"] = emp_code
        if terminal_sn:
            params["terminal_sn"] = terminal_sn

        logger.debug("Fetching transactions page=%d start=%s end=%s", page, start_time, end_time)
        return self._get("/iclock/api/transactions/", params=params)
