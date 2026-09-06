from __future__ import annotations

from datetime import datetime

from src.tasks.map_trade.data import (
    ITEM_ALIASES,
)
from src.tasks.map_trade.models import (
    DEFAULT_RECIPES,
    DEFAULT_SALE_WHITELIST,
    CalendarEntry,
)
from src.tasks.map_trade.progress import UTC_PLUS_8
from src.tasks.map_trade.trader_constants import split_items
from src.tasks.map_trade.vision import normalize_text


class PriceDiscoveryMixin:
    def _sale_whitelist(self) -> set[str]:
        raw = self.task.config.get("出售白名单", ",".join(DEFAULT_SALE_WHITELIST))
        selected_recipes = self.task.config.get("5星料理", list(DEFAULT_RECIPES))
        configured = (
            set(DEFAULT_SALE_WHITELIST)
            | set(split_items(selected_recipes))
            | set(split_items(raw))
        )
        expanded = set(configured)
        for item in configured:
            expanded.update(ITEM_ALIASES.get(item, ()))
        return {self._normal(value) for value in expanded}

    def _sale_blacklist(self) -> set[str]:
        configured = set(split_items(self.task.config.get("出售黑名单", "")))
        expanded = set(configured)
        for item in configured:
            expanded.update(ITEM_ALIASES.get(item, ()))
        return {self._normal(value) for value in expanded}

    def _entry_allowed(self, entry: CalendarEntry, whitelist: set[str]) -> bool:
        names = (entry.item, *entry.aliases, *ITEM_ALIASES.get(entry.item, ()))
        return any(self._normal(value) in whitelist for value in names)

    def _normal(self, value: str) -> str:
        return normalize_text(self.vision.simplify(value))

    def _current_market_time(self) -> datetime:
        provider = getattr(self, "now_provider", None)
        if callable(provider):
            current = provider()
        else:
            current = getattr(self, "started_at", None)
            if current is None:
                current = self.progress.now_provider()
        if current.tzinfo is None:
            return current.replace(tzinfo=UTC_PLUS_8)
        return current.astimezone(UTC_PLUS_8)

