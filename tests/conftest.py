import pytest

from app import main
from app.auth import require_auth


@pytest.fixture(autouse=True)
def _no_real_db_no_auth(monkeypatch):
    """I test usano un database in memoria e (salvo test_auth) saltano il login."""
    monkeypatch.setattr(main, "_ready", True)
    main.app.dependency_overrides[require_auth] = lambda: None
    yield
    main.app.dependency_overrides.clear()
