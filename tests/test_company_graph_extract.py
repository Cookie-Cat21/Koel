"""Unit tests for equity / relation extract heuristics."""

from chime.extractors.company_graph_pdf import (
    GraphExtractResult,
    _clean_name,
    _parse_num,
    extract_company_graph_from_bytes,
)


def test_parse_num_rejects_years():
    assert _parse_num("2024") is None
    assert _parse_num("113,215") == 113215.0
    assert _parse_num("(1,234)") == -1234.0


def test_clean_name_drops_noise():
    assert _clean_name("Directors of Hayleys") is None
    assert _clean_name("Kelani Valley Plantations") is not None


def test_non_financial_skip():
    # Minimal fake PDF bytes will fail text extract → no_text or skip
    result = extract_company_graph_from_bytes(
        b"%PDF-1.4 not a real pdf",
        title="Board Meeting Notice",
        category="Corporate",
        symbol="HAYL.N0000",
    )
    assert isinstance(result, GraphExtractResult)
    assert result.extract_ok is False
    assert result.notes.get("skip") == "not_financial"
