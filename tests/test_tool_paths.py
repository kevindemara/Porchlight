from pathlib import Path

import pytest
from porchlight import config as configuration
from porchlight.config import Config


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
def test_media_tools_follow_profile_before_default_folder_and_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    profile = tmp_path / "profile"
    default_root = tmp_path / "default"
    profile_tool = profile / "tools/ffmpeg/bin" / f"{name}.exe"
    default_tool = default_root / "tools/ffmpeg/bin" / f"{name}.exe"
    for tool in (profile_tool, default_tool):
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.touch()
    monkeypatch.setattr(configuration, "default_data_root", lambda: default_root)
    monkeypatch.setattr(configuration.shutil, "which", lambda _: "path-tool")
    config = Config(data_root=profile)

    assert config.tool_path(name) == str(profile_tool)
    profile_tool.unlink()
    assert config.tool_path(name) == str(default_tool)
    default_tool.unlink()
    assert config.tool_path(name) == "path-tool"


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
def test_explicit_media_tool_keeps_precedence_and_missing_override_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    profile = tmp_path / "profile"
    profile_tool = profile / "tools/ffmpeg/bin" / f"{name}.exe"
    profile_tool.parent.mkdir(parents=True)
    profile_tool.touch()
    explicit = tmp_path / f"custom-{name}.exe"
    explicit.touch()
    monkeypatch.setattr(configuration, "default_data_root", lambda: tmp_path / "default")
    monkeypatch.setattr(configuration.shutil, "which", lambda _: "path-tool")
    config = Config(data_root=profile, **{name: explicit})

    assert config.tool_path(name) == str(explicit.resolve())
    explicit.unlink()
    assert config.tool_path(name) is None
