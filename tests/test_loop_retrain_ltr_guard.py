"""Loop B must not demote LTR/vol champions on hit-rate alone."""

from koel.ml.loop_retrain import _is_ltr_vol_champion_algo


def test_ltr_vol_champion_algo_guard() -> None:
    assert _is_ltr_vol_champion_algo("xgb_pairwise+hgb_vol_gated_ltr")
    assert _is_ltr_vol_champion_algo("hgb_vol")
    assert not _is_ltr_vol_champion_algo("hgb_clf_lmt_bag_gated_c55")
    assert not _is_ltr_vol_champion_algo(None)
    assert not _is_ltr_vol_champion_algo("")
