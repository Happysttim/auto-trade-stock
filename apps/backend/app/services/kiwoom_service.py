from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

from ..config import Settings
from ..database import Database
from ..schemas import AccountSnapshot, BrokerOrderResult, Holding


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_stock_code(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized.startswith("A") and len(normalized) == 7 and normalized[1:].isdigit():
        normalized = normalized[1:]
    if normalized.endswith(".KS") or normalized.endswith(".KQ"):
        normalized = normalized.split(".", 1)[0]
    return normalized


class _SafeTemplateDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_templates(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(_SafeTemplateDict(variables))
    if isinstance(value, list):
        return [_render_templates(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _render_templates(item, variables) for key, item in value.items()}
    return value


class KiwoomBrokerService:
    def __init__(self, settings: Settings, repository: Database) -> None:
        self.settings = settings
        self.repository = repository
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.kiwoom_app_key and self.settings.kiwoom_secret_key)

    @property
    def base_url(self) -> str:
        return self.settings.kiwoom_mock_base_url if self.settings.kiwoom_use_mock else self.settings.kiwoom_base_url

    def _headers(self, api_id: str, *, authorized: bool = True) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
        }
        if authorized:
            headers["authorization"] = f"Bearer {self._ensure_token()}"
        return headers

    def _ensure_token(self) -> str:
        if not self.enabled:
            raise RuntimeError("Kiwoom API credentials are not configured.")

        if (
            self._token
            and self._token_expires_at is not None
            and datetime.now(timezone.utc) + timedelta(minutes=1) < self._token_expires_at
        ):
            return self._token

        response = requests.post(
            f"{self.base_url}/oauth2/token",
            headers={"Content-Type": "application/json;charset=UTF-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kiwoom_app_key,
                "secretkey": self.settings.kiwoom_secret_key,
            },
            timeout=self.settings.kiwoom_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("return_code") not in (None, 0):
            raise RuntimeError(str(payload.get("return_msg") or "Failed to obtain Kiwoom access token."))

        token = str(payload.get("token") or "")
        if not token:
            raise RuntimeError("Kiwoom token response did not include an access token.")

        expires_raw = str(payload.get("expires_dt") or "")
        if expires_raw:
            self._token_expires_at = datetime.strptime(expires_raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        else:
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=6)
        self._token = token
        return token

    def _post(self, *, path: str, api_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{path}",
            headers=self._headers(api_id),
            json=body or {},
            timeout=self.settings.kiwoom_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("return_code") not in (None, 0):
            raise RuntimeError(str(payload.get("return_msg") or f"Kiwoom API request failed for {api_id}."))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Kiwoom API returned an unexpected payload for {api_id}.")
        return payload

    def _iter_dicts(self, payload: Any) -> Iterable[dict[str, Any]]:
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from self._iter_dicts(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_dicts(item)

    def _value_by_aliases(self, payload: dict[str, Any], aliases: Iterable[str]) -> Any:
        alias_set = {_normalize_key(alias) for alias in aliases}
        for key, value in payload.items():
            if _normalize_key(key) in alias_set:
                return value
        return None

    def _extract_account_numbers(self, payload: dict[str, Any]) -> list[str]:
        accounts: list[str] = []
        aliases = ("acctNo", "acct_no", "account_no", "accountNo")
        for item in self._iter_dicts(payload):
            value = self._value_by_aliases(item, aliases)
            if value is None:
                continue
            raw_parts = re.split(r"[,;|\s]+", str(value))
            for part in raw_parts:
                cleaned = part.strip()
                if cleaned and cleaned not in accounts:
                    accounts.append(cleaned)
        return accounts

    def _extract_numeric_candidates(self, payload: dict[str, Any], aliases: Iterable[str]) -> list[float]:
        alias_set = {_normalize_key(alias) for alias in aliases}
        values: list[float] = []
        for item in self._iter_dicts(payload):
            for key, raw_value in item.items():
                if _normalize_key(key) in alias_set:
                    numeric = _parse_float(raw_value)
                    if numeric:
                        values.append(numeric)
        return values

    def _parse_holdings(self, payload: dict[str, Any], account_no: str | None) -> list[Holding]:
        holdings_by_symbol: dict[str, Holding] = {}
        for item in self._iter_dicts(payload):
            symbol = self._value_by_aliases(
                item,
                ("stk_cd", "item_no", "jongmok_code", "code", "symbol"),
            )
            quantity = self._value_by_aliases(
                item,
                ("rmnd_qty", "qty", "holding_qty", "own_qty", "bal_qty", "quantity"),
            )
            normalized_symbol = _normalize_stock_code(symbol)
            quantity_value = int(_parse_float(quantity))
            if not normalized_symbol or quantity_value <= 0:
                continue

            available_quantity = int(
                _parse_float(
                    self._value_by_aliases(
                        item,
                        ("ord_psbl_qty", "sell_psbl_qty", "available_qty", "available_quantity"),
                    )
                )
            ) or quantity_value
            average_price = _parse_float(
                self._value_by_aliases(item, ("avg_prc", "pchs_avg_pric", "average_price", "buy_price"))
            )
            current_price = _parse_float(
                self._value_by_aliases(item, ("cur_prc", "now_pric", "current_price", "price"))
            )
            market_value = _parse_float(
                self._value_by_aliases(item, ("evlt_amt", "market_value", "val_amt", "amount"))
            )
            if market_value <= 0 and current_price > 0:
                market_value = current_price * quantity_value
            pnl_raw = self._value_by_aliases(item, ("evlt_pfls_amt", "pl_amt", "pnl", "profit_loss"))
            pnl = None if pnl_raw is None else _parse_float(pnl_raw)
            company_name = str(
                self._value_by_aliases(item, ("stk_nm", "item_nm", "name", "company_name")) or normalized_symbol
            ).strip()

            holdings_by_symbol[normalized_symbol] = Holding(
                symbol=normalized_symbol,
                company_name=company_name or normalized_symbol,
                quantity=quantity_value,
                available_quantity=available_quantity,
                average_price=average_price,
                current_price=current_price,
                market_value=market_value,
                pnl=pnl,
                account_no=account_no,
            )

        holdings = list(holdings_by_symbol.values())
        holdings.sort(key=lambda item: item.market_value, reverse=True)
        return holdings

    def _extract_cash_balance(self, payload: dict[str, Any]) -> float:
        # Prefer immediately usable cash-style fields so total_equity does not double-count holdings.
        for aliases in (
            ("d2_entra", "ord_psbl_cash", "ord_psbl_amt", "cash_balance", "cash"),
            ("entr",),
        ):
            candidates = self._extract_numeric_candidates(payload, aliases)
            if candidates:
                return max(candidates)
        return self.settings.kiwoom_fallback_cash_balance

    def fetch_account_numbers(self) -> list[str]:
        payload = self._post(
            path="/api/dostk/acnt",
            api_id="ka00001",
            body=self.settings.kiwoom_accounts_body,
        )
        return self._extract_account_numbers(payload)

    def resolve_account_no(self) -> str | None:
        if self.settings.kiwoom_account_no:
            return self.settings.kiwoom_account_no
        accounts = self.fetch_account_numbers()
        return accounts[0] if accounts else None

    def fetch_account_snapshot(self) -> AccountSnapshot:
        account_no = self.resolve_account_no()
        if not account_no:
            raise RuntimeError("Unable to resolve a Kiwoom account number.")

        holdings_payload = _render_templates(
            self.settings.kiwoom_holdings_body,
            {
                "account_no": account_no,
                "exchange_code": self.settings.kiwoom_exchange_code,
            },
        )

        holdings_response = self._post(
            path="/api/dostk/acnt",
            api_id="kt00004",
            body=holdings_payload,
        )
        cash_balance = self._extract_cash_balance(holdings_response)
        holdings = self._parse_holdings(holdings_response, account_no)

        return AccountSnapshot(
            account_no=account_no,
            cash_balance=cash_balance,
            holdings=holdings,
        )

    def _normalize_symbol_for_order(self, symbol: str) -> str | None:
        cleaned = symbol.strip().upper()
        if cleaned.endswith(".KS") or cleaned.endswith(".KQ"):
            cleaned = cleaned.split(".", 1)[0]
        if re.fullmatch(r"\d{6}", cleaned):
            return cleaned
        return None

    def place_market_order(
        self,
        *,
        symbol: str,
        company_name: str,
        action: str,
        quantity: int,
        reference_price: float,
    ) -> BrokerOrderResult:
        if quantity <= 0:
            return BrokerOrderResult(success=False, broker_order_id=None, message="Quantity must be positive.")
        if action not in {"buy", "sell"}:
            return BrokerOrderResult(success=False, broker_order_id=None, message="Unsupported order action.")
        if not self.enabled:
            return BrokerOrderResult(success=False, broker_order_id=None, message="Kiwoom API credentials are not configured.")

        account_no = self.resolve_account_no()
        if not account_no:
            return BrokerOrderResult(success=False, broker_order_id=None, message="Unable to resolve a Kiwoom account number.")

        normalized_symbol = self._normalize_symbol_for_order(symbol)
        if normalized_symbol is None:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                message=f"{symbol} is not a Kiwoom domestic stock code.",
            )

        api_id = "kt10000" if action == "buy" else "kt10001"
        body = {
            "dmst_stex_tp": self.settings.kiwoom_exchange_code,
            "stk_cd": normalized_symbol,
            "ord_qty": str(quantity),
            "ord_uv": "",
            "trde_tp": self.settings.kiwoom_order_type_code,
            "cond_uv": "",
        }
        body.update(
            _render_templates(
                self.settings.kiwoom_order_body,
                {
                    "account_no": account_no,
                    "symbol": normalized_symbol,
                    "quantity": quantity,
                    "action": action,
                    "reference_price": reference_price,
                },
            )
        )

        try:
            payload = self._post(
                path="/api/dostk/ordr",
                api_id=api_id,
                body=body,
            )
        except Exception as exc:
            return BrokerOrderResult(
                success=False,
                broker_order_id=None,
                message=f"Kiwoom order failed: {exc}",
            )

        broker_order_id = str(payload.get("ord_no") or payload.get("ordNo") or "")
        if not broker_order_id:
            broker_order_id = f"{normalized_symbol}-{action}-{int(datetime.now().timestamp())}"

        return BrokerOrderResult(
            success=True,
            broker_order_id=broker_order_id,
            message=str(payload.get("return_msg") or f"{company_name} {action} order submitted to Kiwoom."),
            raw_payload=payload,
        )

    def shutdown(self) -> None:
        self._token = None
        self._token_expires_at = None
