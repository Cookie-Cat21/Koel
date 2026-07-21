"""Pinned challenger catalog tests."""

from __future__ import annotations

from koel.ml.challenger_catalog import CHALLENGERS, challenger_manifest


def test_challenger_catalog_has_unique_immutable_policy_ids() -> None:
    manifest = challenger_manifest()
    assert len(manifest) == len(CHALLENGERS)
    assert len({row["key"] for row in manifest}) == len(manifest)
    assert len({row["policy_id"] for row in manifest}) == len(manifest)
    assert all(len(str(row["revision"])) == 40 for row in manifest)


def test_unlicensed_or_missing_data_challengers_are_blocked() -> None:
    by_key = {spec.key: spec for spec in CHALLENGERS}
    assert by_key["stockmixer"].status == "blocked"
    assert by_key["stockformer"].status == "blocked"
    assert by_key["tlob"].status == "blocked"
    assert by_key["master"].license == "MIT"
    assert by_key["kronos"].license == "MIT"
