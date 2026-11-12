from app.migrate import database_is_ahead


def test_empty_database_is_not_ahead():
    assert database_is_ahead((), {"a1", "b2"}) is False


def test_database_at_a_known_revision_is_not_ahead():
    assert database_is_ahead(("a1",), {"a1", "b2"}) is False


def test_database_with_a_revision_from_a_newer_release_is_ahead():
    assert database_is_ahead(("c3",), {"a1", "b2"}) is True
