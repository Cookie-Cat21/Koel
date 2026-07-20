"""Unit tests for people / role extract heuristics."""

from koel.extractors.people_pdf import (
    _roles_from_blob,
    map_role,
    normalize_person_name,
)


def test_normalize_person_name():
    assert normalize_person_name("Mr. U. G. Madanayake") == "U G MADANAYAKE"
    assert normalize_person_name("MOHAN PANDITHAGE") == "MOHAN PANDITHAGE"


def test_map_role_variants():
    assert map_role("Chairman & Chief Executive") == "chairman"
    assert map_role("Managing Director") == "managing_director"
    assert map_role("Independent Non-Executive Director") == "independent_director"
    assert map_role("Senior Independent Director") == "senior_independent_director"


def test_roles_from_combined_blob():
    roles = _roles_from_blob("Chairman & Chief Executive")
    assert "chairman" in roles and "ceo" in roles
    roles2 = _roles_from_blob("Managing Director & Chief Executive Officer")
    assert "managing_director" in roles2 and "ceo" in roles2
