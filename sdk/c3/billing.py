"""Billing API"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


@dataclass
class Balance:
    total: str
    rewards: str
    paid: str
    available: str

    @classmethod
    def from_dict(cls, data: dict) -> "Balance":
        return cls(
            total=data.get("total_balance", "0"),
            rewards=data.get("rewards_balance", "0"),
            paid=data.get("balance", "0"),
            available=data.get("available_balance", "0"),
        )


@dataclass
class Transaction:
    id: str
    user_id: str
    amount: int
    amount_usd: float
    transaction_type: str
    status: str
    rewards: bool
    job_id: str | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", ""),
            amount=data.get("amount", 0),
            amount_usd=data.get("amount_usd", 0),
            transaction_type=data.get("transaction_type", ""),
            status=data.get("status", ""),
            rewards=data.get("rewards", False),
            job_id=data.get("job_id"),
            created_at=data.get("created_at", ""),
        )


class Billing:
    """Billing API wrapper"""

    def __init__(self, http: "HTTPClient"):
        self._http = http

    def balance(self) -> Balance:
        """Get account balance"""
        data = self._http.get("/api/balance")
        return Balance.from_dict(data)

    def transactions(self, limit: int = 50, page: int = 1) -> list[Transaction]:
        """List transactions"""
        data = self._http.get("/api/tx", params={"page": page, "page_size": limit})
        return [Transaction.from_dict(tx) for tx in data.get("transactions", [])]

    def get_transaction(self, transaction_id: str) -> Transaction:
        """Get a specific transaction"""
        data = self._http.get(f"/api/tx/{transaction_id}")
        return Transaction.from_dict(data)
