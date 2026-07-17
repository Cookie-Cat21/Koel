"""Unit tests for official CSE companyProfile director parsing."""

from __future__ import annotations

from chime.extractors.cse_directors import (
    merge_cse_board,
    parse_cse_person_name,
    roles_from_cse_text,
)


def test_parse_balendra_style_name() -> None:
    display, roles = parse_cse_person_name(
        "K. (Chief Executive Officer/Executive Director)",
        "Balendra",
    )
    assert display == "K. Balendra"
    assert any("chief executive" in r.lower() for r in roles)


def test_parse_finance_director_embedded() -> None:
    display, roles = parse_cse_person_name(
        "T. Finance Director (Executive Director)",
        "Akbar",
    )
    assert display == "T. Akbar"
    assert any("finance" in r.lower() for r in roles)


def test_roles_executive_chairman_ceo() -> None:
    roles = roles_from_cse_text("Executive Chairman / CEO")
    assert "chairman" in roles
    assert "ceo" in roles


def test_roles_non_independent_not_independent() -> None:
    roles = roles_from_cse_text("Non Independent Non-Executive Director")
    assert "independent_director" not in roles
    assert "non_executive_director" in roles


def test_roles_co_chairman() -> None:
    roles = roles_from_cse_text("Co-Chairman")
    assert "deputy_chairman" in roles
    assert "chairman" not in roles


def test_merge_jkh_board_shape() -> None:
    seats = merge_cse_board(
        top_posts=[
            {
                "directorId": 1105,
                "firstName": "K. (Chief Executive Officer/Executive Director)",
                "lastName": "Balendra",
                "designationOther": "Chairman ",
            },
            {
                "directorId": 7310,
                "firstName": "J.G.A. (Group Finance Director/Executive Director) ",
                "lastName": "Cooray",
                "designationOther": "Deputy Chairman",
            },
        ],
        directors=[
            {
                "directorId": 5701,
                "firstName": "A.(Non Independent Non-Executive Director) ",
                "lastName": "Cabraal",
                "description": None,
            },
            {
                "directorId": 14847,
                "firstName": "D.V.R.S. (Senior Independent Director)",
                "lastName": "Fernando",
                "description": None,
            },
        ],
    )
    by_name = {s.display_name: s for s in seats}
    assert "K. Balendra" in by_name
    assert "chairman" in by_name["K. Balendra"].roles
    assert "ceo" in by_name["K. Balendra"].roles or "executive_director" in by_name[
        "K. Balendra"
    ].roles
    assert "J. G. A. Cooray" in by_name
    cooray = by_name["J. G. A. Cooray"]
    assert "deputy_chairman" in cooray.roles
    assert "cfo" in cooray.roles
    cabraal = by_name["A. Cabraal"]
    assert "independent_director" not in cabraal.roles
    assert "non_executive_director" in cabraal.roles
    fernando = by_name["D. V. R. S. Fernando"]
    assert "senior_independent_director" in fernando.roles


def test_dhammika_perera_display_alias() -> None:
    from chime.extractors.cse_directors import parse_cse_director_row

    seat = parse_cse_director_row(
        {
            "directorId": 16085,
            "firstName": "K. A. D. D. (Non Executive Director)",
            "lastName": "Perera",
            "designationOther": "Co-Chairman",
        },
        source_bucket="top_posts",
    )
    assert seat is not None
    assert seat.display_name == "K. A. D. D. Perera"
    assert seat.name_norm == "K A D D PERERA"


def test_merge_hayleys_pandithage() -> None:
    seats = merge_cse_board(
        top_posts=[
            {
                "directorId": 5824,
                "firstName": "M.",
                "lastName": "Pandithage",
                "designationOther": "Executive Chairman / CEO",
            },
            {
                "directorId": 16085,
                "firstName": "K. A. D. D. (Non Executive Director)",
                "lastName": "Perera",
                "designationOther": "Co-Chairman",
            },
        ],
        directors=[],
    )
    by_name = {s.display_name: s for s in seats}
    assert by_name["M. Pandithage"].roles == ("chairman", "ceo") or set(
        by_name["M. Pandithage"].roles
    ) >= {"chairman", "ceo"}
    perera = by_name["K. A. D. D. Perera"]
    assert perera.name_norm == "K A D D PERERA"
    assert "deputy_chairman" in perera.roles
