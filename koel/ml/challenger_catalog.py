"""Pinned upstream challenger catalog and prospective policy identities."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ChallengerSpec:
    key: str
    family: str
    repository: str
    revision: str
    license: str | None
    compute: str
    target: str
    policy_id: str
    status: str
    blocker: str | None = None


CHALLENGERS: tuple[ChallengerSpec, ...] = (
    ChallengerSpec(
        key="qlib_lgb_native",
        family="Qlib LightGBM parity",
        repository="https://github.com/microsoft/qlib",
        revision="da920b7f954f48ab1bb64117c976710de198373e",
        license="MIT",
        compute="cpu",
        target="rank_return",
        policy_id="shadow_policy_rank_qlib_lgb_native_v1",
        status="implemented_native_parity",
    ),
    ChallengerSpec(
        key="double_ensemble_native",
        family="Qlib DoubleEnsemble concept",
        repository="https://github.com/microsoft/qlib",
        revision="da920b7f954f48ab1bb64117c976710de198373e",
        license="MIT",
        compute="cpu",
        target="rank_return",
        policy_id="shadow_policy_rank_qlib_de_native_v1",
        status="implemented_native_approximation",
        blocker="exact parity requires isolated pyqlib 0.9.7 workflow",
    ),
    ChallengerSpec(
        key="qlib_lgb_exact",
        family="Qlib LightGBM exact",
        repository="https://github.com/microsoft/qlib",
        revision="da920b7f954f48ab1bb64117c976710de198373e",
        license="MIT",
        compute="cpu",
        target="rank_return",
        policy_id="shadow_policy_rank_qlib_lgb_v1",
        status="implemented_offline",
    ),
    ChallengerSpec(
        key="qlib_double_ensemble_exact",
        family="Qlib DoubleEnsemble exact",
        repository="https://github.com/microsoft/qlib",
        revision="da920b7f954f48ab1bb64117c976710de198373e",
        license="MIT",
        compute="cpu",
        target="rank_return",
        policy_id="shadow_policy_rank_qlib_de_v1",
        status="implemented_offline",
    ),
    ChallengerSpec(
        key="qlib_tra",
        family="TRA",
        repository="https://github.com/microsoft/qlib",
        revision="da920b7f954f48ab1bb64117c976710de198373e",
        license="MIT",
        compute="gpu",
        target="rank_return",
        policy_id="shadow_policy_rank_tra_v1",
        status="implemented_offline",
        blocker=(
            "evaluated three-fold h1 2026-07-22: RankIC 0.1369 pooled, "
            "below DoubleEnsemble baseline (0.2526); spread not computable "
            "(tied scores every session) -- rejected, see "
            "docs/experiments/GPU_CHALLENGER_20260722.md"
        ),
    ),
    ChallengerSpec(
        key="master",
        family="MASTER",
        repository="https://github.com/SJTU-DMTai/MASTER",
        revision="de8f58557096abde4216a701b35fc4368158d111",
        license="MIT",
        compute="gpu",
        target="rank_return",
        policy_id="shadow_policy_rank_master_v1",
        status="blocked",
        blocker=(
            "adapter implemented and unit-tested, but OOM at hybrid-dataset "
            "scale (dense per-segment window tensor, ~2.5GB/fold) on all "
            "three folds -- not yet evaluated, see "
            "docs/experiments/GPU_CHALLENGER_20260722.md section 3"
        ),
    ),
    ChallengerSpec(
        key="stockmixer",
        family="StockMixer",
        repository="https://github.com/SJTU-DMTai/StockMixer",
        revision="cce13598afd3ff33ae317700a85ae08db0554652",
        license=None,
        compute="gpu",
        target="rank_return",
        policy_id="shadow_policy_rank_stockmixer_v1",
        status="blocked",
        blocker="no repository license detected",
    ),
    ChallengerSpec(
        key="stockformer",
        family="Multitask Stockformer",
        repository="https://github.com/Eric991005/Multitask-Stockformer",
        revision="0a4f78b6982a19c7c4b3473075279011801c5db2",
        license=None,
        compute="gpu",
        target="rank_and_direction",
        policy_id="shadow_policy_rank_stockformer_v1",
        status="blocked",
        blocker="no repository license detected",
    ),
    ChallengerSpec(
        key="kronos",
        family="Kronos mini/base",
        repository="https://github.com/shiyu-coder/Kronos",
        revision="67b630e67f6a18c9e9be918d9b4337c960db1e9a",
        license="MIT",
        compute="gpu",
        target="feature_generator",
        policy_id="shadow_policy_rank_kronos_v1",
        status="implemented_evaluation_in_progress",
        blocker=(
            "adapter implemented and unit-tested (koel/ml/gpu_challengers.py"
            "::predict_kronos_features); full three-fold h1 run in progress "
            "as of 2026-07-22, see "
            "docs/experiments/GPU_CHALLENGER_20260722.md section 4 -- "
            "update this status once that run completes"
        ),
    ),
    ChallengerSpec(
        key="tlob",
        family="TLOB",
        repository="https://github.com/LeonardoBerti00/TLOB",
        revision="f1c0af4d81067978914361766db0457a7d8b6a46",
        license="MIT",
        compute="gpu",
        target="lob_event_direction",
        policy_id="shadow_policy_lob_tlob_v1",
        status="blocked",
        blocker="CSE public feed lacks multi-level event book data",
    ),
    ChallengerSpec(
        key="de_persist_native",
        family="Native DoubleEnsemble + persistence book",
        repository="https://github.com/ArdenoStudio/Koel",
        revision="7ac28d6a4e3b101d5750609c42649d29fc85d6a3",
        license=None,
        compute="cpu",
        target="rank_return",
        policy_id="shadow_policy_rank_de_persist_v1",
        status="loop0_shadow_wired",
        blocker=(
            "Loop-0 ledger only: relative/h1 double_ensemble_native with "
            "persistence_exit_10_top_bottom_05; offline split-adjusted "
            "net@112bps +0.49%; not user-facing until global gates pass"
        ),
    ),
    ChallengerSpec(
        key="de_h3_weekly_native",
        family="Native DoubleEnsemble + h3 weekly book",
        repository="https://github.com/ArdenoStudio/Koel",
        revision="50400d9bd4bf5a9e0e7945ef34d536b35ecdc8ed",
        license=None,
        compute="cpu",
        target="rank_return_h3",
        policy_id="shadow_policy_rank_de_h3_weekly_v1",
        status="loop0_shadow_wired",
        blocker=(
            "Loop-0 ledger only: relative/h3 double_ensemble_native with "
            "weekly_5_sessions_top_bottom_05; offline split-adjusted "
            "net@112bps +0.27%; not user-facing and does not meet the "
            "selective 90% SuccessContract"
        ),
    ),
)


def challenger_manifest() -> list[dict[str, object]]:
    keys = [spec.key for spec in CHALLENGERS]
    policies = [spec.policy_id for spec in CHALLENGERS]
    if len(set(keys)) != len(keys) or len(set(policies)) != len(policies):
        raise ValueError("challenger keys and policy IDs must be unique")
    return [asdict(spec) for spec in CHALLENGERS]
