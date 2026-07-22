"""Source contract — koel-native chart overlays (not a TradingView clone)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "web" / "src" / "lib" / "charts" / "koel-chart-events.ts"
LWC = ROOT / "web" / "src" / "components" / "charts" / "lwc-price-chart.tsx"
EXPAND = ROOT / "web" / "src" / "components" / "charts" / "expandable-price-chart.tsx"
LAYERS = ROOT / "docs" / "factory" / "CHART_LAYERS.md"


def test_koel_chart_events_helpers_exist() -> None:
    src = EVENTS.read_text(encoding="utf-8")
    assert "buildDisclosureMarkers" in src
    assert "buildFireMarkers" in src
    assert "buildThresholdLines" in src
    assert "price_above" in src
    assert "Asia/Colombo" in src


def test_lwc_accepts_koel_overlays() -> None:
    src = LWC.read_text(encoding="utf-8")
    assert "createSeriesMarkers" in src
    assert "createPriceLine" in src
    assert "markers" in src
    assert "priceLines" in src
    assert "Telegram fire" in src or "violet" in src


def test_expand_dialog_toggles_koel_overlays() -> None:
    src = EXPAND.read_text(encoding="utf-8")
    assert "Disclosures" in src
    assert "Fires" in src
    assert "Alert lines" in src
    assert "initialDisclosures" in src
    assert "/api/v1/alerts/history" in src
    assert "SMA 20" in src
    assert "H-line" in src
    assert "seriesStyle" in src


def test_chart_layers_doc_names_koel_plus() -> None:
    src = LAYERS.read_text(encoding="utf-8")
    assert "koel-native overlays" in src
    assert "TV-inspired koel workbench" in src
