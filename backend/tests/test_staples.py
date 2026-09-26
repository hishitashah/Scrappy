"""Assumed staples (spec section 4): water, and nothing else."""

from sqlalchemy.orm import Session

from app.staples import ASSUMED_STAPLE_NAMES, staple_ingredient_ids


def test_water_is_the_only_assumed_staple() -> None:
    assert ASSUMED_STAPLE_NAMES == frozenset({"water"})


def test_staple_ids_resolve_against_the_catalog(session: Session, catalog: dict[str, int]) -> None:
    assert staple_ingredient_ids(session) == [catalog["water"]]


def test_no_staples_before_the_catalog_is_imported(session: Session) -> None:
    assert staple_ingredient_ids(session) == []
