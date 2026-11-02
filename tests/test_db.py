import pytest

from app.db import normalize


@pytest.mark.parametrize("url", ["postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"])
def test_postgres_urls_get_the_psycopg_driver(url):
    assert normalize(url) == "postgresql+psycopg://u:p@h:5432/d"


def test_other_urls_are_untouched():
    assert normalize("sqlite:///budget.db") == "sqlite:///budget.db"
    assert normalize("postgresql+psycopg://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
