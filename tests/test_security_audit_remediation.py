"""Source pins for security audit remediation (S-01, S-04, S-05, S-07, S-11)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_s01_api_session_revoke_in_guard() -> None:
    guard = (WEB / "src" / "lib" / "auth" / "guard.ts").read_text(encoding="utf-8")
    assert "export async function requireSession" in guard
    assert "export async function requireSessionAndCsrf" in guard
    assert "isDashSessionRevoked" in guard
    assert 'jsonError(401, "unauthorized"' in guard
    assert 'jsonError(503, "degraded"' in guard
    # All API call sites must await.
    api_root = WEB / "src" / "app" / "api"
    for path in api_root.rglob("route.ts"):
        src = path.read_text(encoding="utf-8")
        if "requireSession" not in src and "requireSessionAndCsrf" not in src:
            continue
        assert "await requireSession(" in src or "await requireSessionAndCsrf(" in src, path
        assert "const gated = requireSession(" not in src
        assert "const gated = requireSessionAndCsrf(" not in src


def test_s11_uniform_demo_auth_denied() -> None:
    demo = (
        WEB / "src" / "app" / "api" / "v1" / "auth" / "demo" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "demo_auth_denied" in demo
    assert "telegram_id_not_allowlisted" not in demo
    assert "Demo sign-in is not available for this Telegram ID." in demo
    cfg = (WEB / "src" / "lib" / "auth" / "config.ts").read_text(encoding="utf-8")
    assert "showDemoAllowlist" in cfg
    assert "DASH_DEMO_SHOW_ALLOWLIST" in cfg
    assert "if (!cfg.showDemoAllowlist) return []" in cfg


def test_s07_announce_bar_no_inline_script() -> None:
    bar = (
        WEB / "src" / "components" / "marketing" / "announcement-bar.tsx"
    ).read_text(encoding="utf-8")
    assert "dangerouslySetInnerHTML" not in bar
    assert "useEffect" in bar
    assert "sessionStorage" in bar


def test_s04_auth_rate_limit_wired() -> None:
    rl = (WEB / "src" / "lib" / "auth" / "rate-limit.ts").read_text(encoding="utf-8")
    assert "hitRateLimit" in rl
    assert "clientIpFromRequest" in rl
    demo = (
        WEB / "src" / "app" / "api" / "v1" / "auth" / "demo" / "route.ts"
    ).read_text(encoding="utf-8")
    telegram = (
        WEB / "src" / "app" / "api" / "v1" / "auth" / "telegram" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "hitRateLimit" in demo and "rate_limited" in demo
    assert "hitRateLimit" in telegram and "rate_limited" in telegram


def test_s05_health_ops_gate() -> None:
    health = (
        WEB / "src" / "app" / "api" / "v1" / "health" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "isOpsTelegramId" in health
    assert "DASH_OPS_TELEGRAM_IDS" in (
        WEB / "src" / "lib" / "auth" / "config.ts"
    ).read_text(encoding="utf-8") or "opsAllowlist" in (
        WEB / "src" / "lib" / "auth" / "config.ts"
    ).read_text(encoding="utf-8")
    assert 'detail: false' in health or "detail: false" in health
    assert "opsDetail" in health


def test_security_rotation_runbook_exists() -> None:
    path = ROOT / "docs" / "runbooks" / "SECURITY_ROTATION.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "DASH_DEMO_AUTH=0" in text
    assert "TELEGRAM_BOT_TOKEN" in text
