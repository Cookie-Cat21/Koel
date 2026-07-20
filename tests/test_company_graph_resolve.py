"""Fail-closed name → symbol resolution for company graph."""

from koel.graph.resolve import (
    build_suffix_map,
    maps_from_stock_pairs,
    resolve_company_name,
    strip_legal_suffix,
)


def test_strip_legal_suffix():
    assert strip_legal_suffix("ACL CABLES PLC") == "ACL CABLES"
    assert strip_legal_suffix("HAYLEYS LIMITED") == "HAYLEYS"


def test_exact_and_suffix_resolve():
    pairs = [
        ("ACL.N0000", "ACL CABLES PLC"),
        ("APLA.N0000", "ACL PLASTICS PLC"),
        ("HAYL.N0000", "HAYLEYS PLC"),
    ]
    exact, suffix = maps_from_stock_pairs(pairs)
    assert resolve_company_name(
        "ACL CABLES PLC", exact_map=exact, suffix_map=suffix
    ).symbol == "ACL.N0000"
    assert resolve_company_name(
        "ACL Plastics", exact_map=exact, suffix_map=suffix
    ).symbol == "APLA.N0000"
    assert resolve_company_name(
        "Hayleys PLC", exact_map=exact, suffix_map=suffix
    ).symbol == "HAYL.N0000"


def test_voting_share_preferred_on_dual_list():
    pairs = [
        ("COMB.N0000", "COMMERCIAL BANK OF CEYLON PLC"),
        ("COMB.X0000", "COMMERCIAL BANK OF CEYLON PLC"),
    ]
    exact, suffix = maps_from_stock_pairs(pairs)
    assert exact.get("COMMERCIAL BANK OF CEYLON PLC") == "COMB.N0000"
    r = resolve_company_name(
        "Commercial Bank of Ceylon PLC",
        exact_map=exact,
        suffix_map=suffix,
    )
    assert r.symbol == "COMB.N0000"


def test_truly_ambiguous_names_still_dropped():
    pairs = [
        ("A.N0000", "SAME NAME PLC"),
        ("B.N0000", "SAME NAME PLC"),
    ]
    exact, _suffix = maps_from_stock_pairs(pairs)
    assert "SAME NAME PLC" not in exact


def test_suffix_map_unique_only():
    exact = {
        "FOO HOLDINGS PLC": "FOO.N0000",
        "BAR PLC": "BAR.N0000",
    }
    sm = build_suffix_map(exact)
    assert sm.get("FOO") == "FOO.N0000" or sm.get("FOO HOLDINGS") == "FOO.N0000"
