#!/usr/bin/env python
"""Regression check for manual payment approval upgrades."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import db_supabase as db


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, supabase, table_name: str):
        self.supabase = supabase
        self.table_name = table_name
        self._op = None
        self._payload = None
        self._field = None
        self._value = None

    def select(self, *_args):
        self._op = "select"
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, field, value):
        self._field = field
        self._value = value
        return self

    def execute(self):
        if self.table_name == "payment_attempts" and self._op == "select":
            record = self.supabase.payment_attempts.get(self._value)
            return _FakeResponse([record] if record else [])

        if self.table_name == "payment_attempts" and self._op == "update":
            record = self.supabase.payment_attempts.get(self._value)
            if record:
                record.update(self._payload or {})
                self.supabase.applied_updates.append((self._value, dict(self._payload or {})))
            return _FakeResponse([{}])

        return _FakeResponse([])


class _FakeSupabase:
    def __init__(self):
        self.payment_attempts = {
            "TX_UPGRADE_001": {
                "tx_id": "TX_UPGRADE_001",
                "telegram_id": 123456789,
                "plan_requested": "max_yearly",
                "status": "PENDING",
            }
        }
        self.applied_updates = []

    def table(self, table_name: str):
        return _FakeTable(self, table_name)


def main() -> int:
    fake_supabase = _FakeSupabase()
    captured_user_update = {}

    original_get_supabase = db._get_supabase
    original_update_user = db.update_user
    try:
        db._get_supabase = lambda: fake_supabase

        def _fake_update_user(telegram_id: int, updates: dict) -> bool:
            captured_user_update["telegram_id"] = telegram_id
            captured_user_update["updates"] = dict(updates)
            return True

        db.update_user = _fake_update_user

        approved = db.approve_payment("TX_UPGRADE_001")
        assert approved is True, "approve_payment returned False"
        assert captured_user_update["telegram_id"] == 123456789
        updates = captured_user_update["updates"]
        assert updates["tier"] == "max"
        assert updates["subscription_active"] is True
        assert updates["subscription_expires_at"], "missing expiry"
        assert updates["tier_updated_at"], "missing tier_updated_at"

        expiry = datetime.fromisoformat(updates["subscription_expires_at"])
        delta_days = (expiry - datetime.now(timezone.utc)).days
        assert 364 <= delta_days <= 366, f"unexpected expiry window: {delta_days} days"

        stored = fake_supabase.payment_attempts["TX_UPGRADE_001"]
        assert stored["status"] == "APPROVED"
        print("[OK] Manual approval upgrades the user tier and marks the payment approved.")
        return 0
    finally:
        db._get_supabase = original_get_supabase
        db.update_user = original_update_user


if __name__ == "__main__":
    raise SystemExit(main())