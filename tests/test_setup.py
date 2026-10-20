import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from porchlight.ai import readiness


@pytest.mark.parametrize(
    "ram,gpu,tier,model",
    [
        (None, None, "unknown", None),
        (8, 16, "skip", None),
        (14, None, "skip", None),
        (16, None, "cpu", "qwen3-vl:4b"),
        (16, 4, "cpu", "qwen3-vl:4b"),
        (16, 8, "light", "qwen3-vl:4b"),
        (16, 16, "light", "qwen3-vl:4b"),
        (32, 12, "balanced", "qwen3-vl:8b"),
    ],
)
def test_readiness_is_only_a_conservative_candidate(
    ram: int | None, gpu: int | None, tier: str, model: str | None
) -> None:
    view = readiness.recommend(
        ram * readiness.GIB if ram else None, gpu * readiness.GIB if gpu else None, 8
    )
    assert view.recommendation == tier and view.suggested_model == model
    assert view.suggested_workload == ("balanced" if tier == "balanced" else "light")
    assert not any(name in view.model_dump() for name in ("enabled", "compatible", "passed"))


def test_gpu_probe_is_bounded_and_does_not_sum_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(readiness.shutil, "which", lambda name: "synthetic-nvidia-smi")

    def run(args: list[str], **kwargs: object) -> SimpleNamespace:
        assert args == [
            "synthetic-nvidia-smi",
            "--query-gpu=memory.total",
            "--format=csv,noheader,nounits",
        ]
        assert kwargs["timeout"] == 3 and kwargs.get("shell") is None
        return SimpleNamespace(stdout="8192\n4096\n")

    monkeypatch.setattr(readiness.subprocess, "run", run)
    assert readiness.gpu_bytes() == 8 * readiness.GIB

    def timed_out(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("synthetic", 3)

    monkeypatch.setattr(readiness.subprocess, "run", timed_out)
    assert readiness.gpu_bytes() is None
    monkeypatch.setattr(readiness.shutil, "which", lambda name: None)
    assert readiness.gpu_bytes() is None


def test_setup_read_only_checks_are_authenticated_and_do_not_enable_ai(
    authenticated: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = authenticated
    before = client.get("/api/v1/settings").json()
    monkeypatch.setattr(
        "porchlight.app.inspect_machine", lambda: readiness.recommend(8 * readiness.GIB, None, 4)
    )
    result = client.get("/api/v1/setup/ai-readiness")
    assert result.status_code == 200 and result.json()["recommendation"] == "skip"
    assert client.get("/api/v1/settings").json() == before
    for name in ("quick-start", "local-ai", "phone", "direct-https", "cloudflare-backup"):
        guide = client.get(f"/api/v1/setup/guides/{name}")
        assert guide.status_code == 200 and guide.headers["cache-control"] == "no-store"
        assert "attachment" in guide.headers["content-disposition"]
    assert client.get("/api/v1/setup/guides/README.md").status_code == 422
    assert client.get("/api/v1/setup/guides/%2e%2e%2fconfig.py").status_code == 404
    client.cookies.clear()
    assert client.get("/api/v1/setup/ai-readiness").status_code == 401
    for name in ("phone", "direct-https", "cloudflare-backup"):
        assert client.get(f"/api/v1/setup/guides/{name}").status_code == 401


def test_new_setup_docs_have_resolvable_local_links() -> None:
    import re

    from porchlight.config import ROOT

    for name in (
        "QUICK_START.md",
        "LOCAL_AI_SETUP.md",
        "PHONE_SETUP.md",
        "DIRECT_HTTPS.md",
        "CLOUDFLARE_BACKUP.md",
    ):
        path = ROOT / "docs" / name
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not target.startswith("https:"):
                assert (path.parent / target).is_file(), (name, target)
