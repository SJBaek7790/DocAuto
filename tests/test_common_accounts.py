import os
import pytest
from common import list_accounts, account_label, is_recon_enabled, KST

def test_list_accounts():
    creds = {
        "telegram": {"bot_token": "xxx"},
        "bjh7790": {"label": "승진", "doctorville": {}, "hmp": {}},
        "wonju": {"doctorville": {}}
    }
    assert list_accounts(creds) == ["bjh7790", "wonju"]
    assert list_accounts(creds, site="hmp") == ["bjh7790"]
    assert list_accounts(creds, site="doctorville") == ["bjh7790", "wonju"]

def test_account_label():
    creds = {
        "bjh7790": {"label": "승진"},
        "wonju": {}
    }
    assert account_label(creds, "bjh7790") == "승진"
    assert account_label(creds, "wonju") == "wonju"

def test_is_recon_enabled(monkeypatch):
    monkeypatch.setenv("RECON", "1")
    assert is_recon_enabled() is True
    monkeypatch.delenv("RECON", raising=False)
    assert is_recon_enabled() is False

def test_kst_timezone():
    assert KST.utcoffset(None).total_seconds() == 9 * 3600
