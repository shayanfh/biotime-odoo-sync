import logging
import xmlrpc.client
from typing import Any

logger = logging.getLogger(__name__)


class OdooClient:
    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password

        logger.info("Authenticating to Odoo at %s", self.url)
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        uid = common.authenticate(self.db, self.username, self.password, {})

        if not uid:
            raise RuntimeError("Odoo authentication failed — check credentials and db name")

        self.uid = uid
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        logger.info("Odoo authentication successful (uid=%d)", self.uid)

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"fields": fields}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute_kw(model=model, method="search_read", args=[domain], kwargs=kwargs)

    def create(self, model: str, vals: dict[str, Any]) -> int:
        return self.execute_kw(model=model, method="create", args=[vals])

    def write(self, model: str, record_ids: list[int], vals: dict[str, Any]) -> bool:
        return self.execute_kw(model=model, method="write", args=[record_ids, vals])

    def fields_get(self, model: str) -> dict[str, Any]:
        return self.execute_kw(
            model=model,
            method="fields_get",
            args=[],
            kwargs={"attributes": ["string", "type", "required", "readonly"]},
        )
