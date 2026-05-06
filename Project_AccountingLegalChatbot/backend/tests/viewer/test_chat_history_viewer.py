"""Unit tests for chat_history_viewer._find_db_path()."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import from the viewer script (one level up from backend/)
_VIEWER = Path(__file__).parent.parent.parent.parent / "chat_history_viewer.py"
sys.path.insert(0, str(_VIEWER.parent))

import importlib.util
spec = importlib.util.spec_from_file_location("chat_history_viewer", _VIEWER)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)
_find_db_path = _mod._find_db_path


def test_env_var_takes_priority(tmp_path):
    """CHATBOT_DB_PATH env var is returned immediately when set and file exists."""
    db = tmp_path / "custom.db"
    db.touch()
    with patch.dict(os.environ, {"CHATBOT_DB_PATH": str(db)}):
        assert _find_db_path() == db


def test_env_var_ignored_when_file_missing(tmp_path, monkeypatch):
    """CHATBOT_DB_PATH is skipped when the file does not exist; chatbot_local used instead."""
    monkeypatch.setenv("CHATBOT_DB_PATH", str(tmp_path / "nonexistent.db"))
    expected = Path.home() / "chatbot_local" / "Project_AccountingLegalChatbot" / "backend" / "data" / "chatbot.db"
    with patch.object(Path, "exists", lambda p: str(p) == str(expected)):
        result = _find_db_path()
    assert "chatbot_local" in str(result)


def test_chatbot_local_path_found_when_exists(tmp_path, monkeypatch):
    """chatbot_local path is returned when CHATBOT_DB_PATH not set and file exists there."""
    monkeypatch.delenv("CHATBOT_DB_PATH", raising=False)
    expected = Path.home() / "chatbot_local" / "Project_AccountingLegalChatbot" / "backend" / "data" / "chatbot.db"
    def patched_exists(self):
        return str(self) == str(expected)
    with patch.object(Path, "exists", patched_exists):
        result = _find_db_path()
    assert result == expected


def test_script_relative_path_fallback(tmp_path, monkeypatch):
    """Falls back to <script_dir>/backend/data/chatbot.db when chatbot_local doesn't exist."""
    monkeypatch.delenv("CHATBOT_DB_PATH", raising=False)
    script_relative = Path(_VIEWER.parent) / "backend" / "data" / "chatbot.db"
    def patched_exists(self):
        return str(self) == str(script_relative)
    with patch.object(Path, "exists", patched_exists):
        result = _find_db_path()
    assert result == script_relative


def test_returns_none_when_nothing_found(monkeypatch):
    """Returns None when no candidate path exists (caller should show error)."""
    monkeypatch.delenv("CHATBOT_DB_PATH", raising=False)
    with patch.object(Path, "exists", lambda _: False):
        result = _find_db_path()
    assert result is None


def test_parent_dir_path_fallback(monkeypatch):
    """Falls back to <script_dir>/../backend/data/chatbot.db as last resort."""
    monkeypatch.delenv("CHATBOT_DB_PATH", raising=False)
    parent_relative = Path(_VIEWER.parent).parent / "backend" / "data" / "chatbot.db"
    with patch.object(Path, "exists", lambda p: str(p) == str(parent_relative)):
        result = _find_db_path()
    assert result == parent_relative
