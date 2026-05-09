import os

from config import Settings


def test_config_has_source_dir_settings():
    """Config must expose source_law_dir, source_finance_dir, entity_graph_db."""
    s = Settings()
    assert hasattr(s, "source_law_dir")
    assert hasattr(s, "source_finance_dir")
    assert hasattr(s, "entity_graph_db")


def test_source_dirs_default_to_backend_relative():
    """Default paths must resolve to absolute paths under backend/."""
    s = Settings()
    assert os.path.isabs(s.source_law_dir), "source_law_dir must be absolute"
    assert os.path.isabs(s.source_finance_dir), "source_finance_dir must be absolute"
    assert os.path.isabs(s.entity_graph_db), "entity_graph_db must be absolute"
