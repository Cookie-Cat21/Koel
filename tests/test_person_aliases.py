"""CSE director merge keys — display stays initials, not common names."""

from __future__ import annotations

from chime.extractors.cse_directors import parse_cse_director_row
from chime.extractors.person_aliases import alias_merge_key, preferred_display_name


def test_display_keeps_initials() -> None:
    assert preferred_display_name("M. Pandithage", "M PANDITHAGE") == "M. Pandithage"
    assert preferred_display_name("K. Balendra", "K BALENDRA") == "K. Balendra"
    assert (
        preferred_display_name("K. A. D. D. Perera", "K A D D PERERA")
        == "K. A. D. D. Perera"
    )


def test_pandithage_and_balendra_merge_keys() -> None:
    assert alias_merge_key("M PANDITHAGE") == alias_merge_key("A M PANDITHAGE")
    assert alias_merge_key("K BALENDRA") == alias_merge_key("K N J BALENDRA")
    assert alias_merge_key("D S T JAYAWARDENA") == alias_merge_key(
        "DON S T JAYAWARDENA"
    )
    assert alias_merge_key("K A D B PERERA") is None
    assert alias_merge_key("K A D D PERERA") == "kadd_perera"


def test_parse_keeps_initials_display() -> None:
    seat = parse_cse_director_row(
        {
            "directorId": 5824,
            "firstName": "M.",
            "lastName": "Pandithage",
            "designationOther": "Executive Chairman / CEO",
        },
        source_bucket="top_posts",
    )
    assert seat is not None
    assert seat.display_name == "M. Pandithage"
    assert seat.name_norm == "M PANDITHAGE"

    dham = parse_cse_director_row(
        {
            "directorId": 16085,
            "firstName": "K. A. D. D. (Non Executive Director)",
            "lastName": "Perera",
            "designationOther": "Co-Chairman",
        },
        source_bucket="top_posts",
    )
    assert dham is not None
    assert dham.display_name == "K. A. D. D. Perera"
    assert dham.name_norm == "K A D D PERERA"
