from app.agent import location_hints


def test_neighborhood_is_detected(monkeypatch):
    monkeypatch.setattr(
        location_hints, "_load",
        lambda: ({"caetes": "Caetés", "centro": "Centro"}, {"olinda", "recife"}),
    )
    assert "Caetés" in location_hints.neighborhood_hint("e em caetes?")


def test_municipality_is_not_a_hint(monkeypatch):
    monkeypatch.setattr(
        location_hints, "_load",
        lambda: ({"olinda": "Olinda", "caetes": "Caetés"}, {"olinda"}),
    )
    assert location_hints.neighborhood_hint("UCs em Olinda") is None


def test_no_database_means_no_hint(monkeypatch):
    monkeypatch.setattr(location_hints, "_load", lambda: ({}, set()))
    assert location_hints.neighborhood_hint("e em Caetés?") is None
