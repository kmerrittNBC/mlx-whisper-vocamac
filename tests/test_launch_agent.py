from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

import pytest

from mlx_whisper_vocamac.launch_agent import (
    LABEL,
    LaunchAgentError,
    LaunchAgentManager,
)


class FakeLaunchctl:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.loaded = False

    def __call__(self, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        operation = command[1]
        if operation == "print":
            return subprocess.CompletedProcess(
                command,
                0 if self.loaded else 113,
                stdout=f"service = {LABEL}\n" if self.loaded else "",
                stderr="" if self.loaded else "service not found",
            )
        if operation == "bootstrap":
            self.loaded = True
        elif operation == "bootout":
            self.loaded = False
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def make_manager(tmp_path: Path, runner: FakeLaunchctl) -> LaunchAgentManager:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    python = checkout / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("python")
    python.chmod(0o755)
    ffmpeg = tmp_path / "homebrew" / "bin" / "ffmpeg"
    ffmpeg.parent.mkdir(parents=True)
    ffmpeg.write_text("ffmpeg")
    ffmpeg.chmod(0o755)
    return LaunchAgentManager(
        checkout=checkout,
        python=python,
        ffmpeg=ffmpeg,
        home=tmp_path / "home",
        uid=501,
        runner=runner,
        platform_name="darwin",
    )


def test_install_writes_selected_checkout_and_throttles_unexpected_restarts(
    tmp_path: Path,
) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)

    manager.install()

    plist = plistlib.loads(manager.plist_path.read_bytes())
    assert plist["Label"] == LABEL
    assert plist["ProgramArguments"] == [
        str(manager.python),
        "-m",
        "mlx_whisper_vocamac.cli",
    ]
    assert plist["WorkingDirectory"] == str(manager.checkout)
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist["ThrottleInterval"] == 30
    assert plist["StandardOutPath"].startswith(str(manager.home))
    assert plist["StandardErrorPath"].startswith(str(manager.home))
    assert plist["EnvironmentVariables"]["HF_HOME"].startswith(str(manager.home))
    assert str(manager.ffmpeg.parent) in plist["EnvironmentVariables"]["PATH"]
    assert plist["Umask"] == 0o077
    assert not Path(plist["StandardOutPath"]).is_relative_to(manager.checkout)
    assert not Path(plist["EnvironmentVariables"]["HF_HOME"]).is_relative_to(manager.checkout)
    assert runner.calls == [
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "bootstrap", "gui/501", str(manager.plist_path)],
        ["launchctl", "kickstart", f"gui/501/{LABEL}"],
    ]


def test_reinstall_reloads_updated_plist_and_restart_is_explicit(tmp_path: Path) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)
    manager.install()
    runner.calls.clear()

    manager.install()
    manager.restart()

    assert runner.calls == [
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "bootout", f"gui/501/{LABEL}"],
        ["launchctl", "bootstrap", "gui/501", str(manager.plist_path)],
        ["launchctl", "kickstart", f"gui/501/{LABEL}"],
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "kickstart", "-k", f"gui/501/{LABEL}"],
    ]


def test_start_stop_and_status_are_safe_to_repeat(tmp_path: Path) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)
    manager.install()
    runner.calls.clear()

    manager.stop()
    manager.stop()
    manager.start()
    manager.start()
    status = manager.status()

    assert "service = " + LABEL in status
    assert runner.calls == [
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "bootout", f"gui/501/{LABEL}"],
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "bootstrap", "gui/501", str(manager.plist_path)],
        ["launchctl", "kickstart", f"gui/501/{LABEL}"],
        ["launchctl", "print", f"gui/501/{LABEL}"],
        ["launchctl", "kickstart", f"gui/501/{LABEL}"],
        ["launchctl", "print", f"gui/501/{LABEL}"],
    ]


def test_uninstall_is_idempotent_and_preserves_logs_and_model_cache(tmp_path: Path) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)
    manager.install()
    logs = manager.log_dir / "service.log"
    cache = manager.cache_dir / "models" / "weights.safetensors"
    logs.parent.mkdir(parents=True, exist_ok=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    logs.write_text("operational logs")
    cache.write_text("model weights")

    manager.uninstall()
    manager.uninstall()

    assert not manager.plist_path.exists()
    assert logs.read_text() == "operational logs"
    assert cache.read_text() == "model weights"


def test_install_reports_missing_python_or_ffmpeg_before_registering_job(
    tmp_path: Path,
) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)
    manager.ffmpeg.unlink()

    with pytest.raises(LaunchAgentError, match="FFmpeg.*brew install ffmpeg"):
        manager.install()

    assert not manager.plist_path.exists()
    assert runner.calls == []


def test_install_reports_missing_python_before_registering_job(tmp_path: Path) -> None:
    runner = FakeLaunchctl()
    manager = make_manager(tmp_path, runner)
    manager.python.unlink()

    with pytest.raises(LaunchAgentError, match="Python environment is missing.*uv sync"):
        manager.install()

    assert not manager.plist_path.exists()
    assert runner.calls == []


def test_launchctl_failure_is_actionable(tmp_path: Path) -> None:
    class FailedLaunchctl(FakeLaunchctl):
        def __call__(
            self, command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            self.calls.append(command)
            if command[1] == "print":
                return subprocess.CompletedProcess(
                    command, 113, stdout="", stderr="service not found"
                )
            return subprocess.CompletedProcess(command, 5, stdout="", stderr="permission denied")

    manager = make_manager(tmp_path, FailedLaunchctl())

    with pytest.raises(LaunchAgentError, match="launchctl bootstrap.*permission denied"):
        manager.install()


def test_stop_does_not_hide_unexpected_launchctl_status_failure(tmp_path: Path) -> None:
    class UnavailableLaunchctl(FakeLaunchctl):
        def __call__(
            self, command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            self.calls.append(command)
            return subprocess.CompletedProcess(command, 5, stdout="", stderr="permission denied")

    runner = UnavailableLaunchctl()
    manager = make_manager(tmp_path, runner)

    with pytest.raises(LaunchAgentError, match="launchctl print.*permission denied"):
        manager.stop()

    assert len(runner.calls) == 1
