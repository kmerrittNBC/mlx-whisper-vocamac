from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

LABEL = "com.anodyine.mlx-whisper-vocamac"
PLIST_NAME = f"{LABEL}.plist"
RESTART_THROTTLE_SECONDS = 30
SYSTEM_PATHS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")

Runner = Callable[..., subprocess.CompletedProcess[str]]


class LaunchAgentError(RuntimeError):
    """An actionable failure while managing the per-user LaunchAgent."""


class LaunchAgentManager:
    def __init__(
        self,
        *,
        checkout: Path,
        python: Path,
        ffmpeg: Path | None,
        home: Path,
        uid: int,
        runner: Runner = subprocess.run,
        launchctl: str = "launchctl",
        platform_name: str = sys.platform,
    ) -> None:
        self.checkout = checkout.absolute()
        self.python = python.absolute()
        self.ffmpeg = ffmpeg.absolute() if ffmpeg is not None else None
        self.home = home.absolute()
        self.uid = uid
        self.runner = runner
        self.launchctl = launchctl
        self.platform_name = platform_name

    @property
    def plist_path(self) -> Path:
        return self.home / "Library" / "LaunchAgents" / PLIST_NAME

    @property
    def log_dir(self) -> Path:
        return self.home / "Library" / "Logs" / "mlx-whisper-vocamac"

    @property
    def cache_dir(self) -> Path:
        return self.home / ".cache" / "huggingface"

    @property
    def domain(self) -> str:
        return f"gui/{self.uid}"

    @property
    def target(self) -> str:
        return f"{self.domain}/{LABEL}"

    def install(self) -> str:
        self._validate_install_prerequisites()
        self._ensure_directories()
        self._write_plist()
        if self._is_loaded():
            self._execute("bootout", self.target)
        self._execute("bootstrap", self.domain, str(self.plist_path))
        self._execute("kickstart", self.target)
        return f"Installed and started {LABEL}; it will also start at login."

    def start(self) -> str:
        self._ensure_platform()
        if not self.plist_path.is_file():
            raise LaunchAgentError(
                f"{LABEL} is not installed; run `uv run mlx-whisper-vocamac-agent install` "
                "from the selected checkout."
            )
        if not self._is_loaded():
            self._execute("bootstrap", self.domain, str(self.plist_path))
        self._execute("kickstart", self.target)
        return f"Started {LABEL}."

    def stop(self) -> str:
        self._ensure_platform()
        if self._is_loaded():
            self._execute("bootout", self.target)
        return f"Stopped {LABEL}."

    def restart(self) -> str:
        self._ensure_platform()
        if not self.plist_path.is_file():
            raise LaunchAgentError(
                f"{LABEL} is not installed; run `uv run mlx-whisper-vocamac-agent install` "
                "from the selected checkout."
            )
        if self._is_loaded():
            self._execute("kickstart", "-k", self.target)
        else:
            self._execute("bootstrap", self.domain, str(self.plist_path))
            self._execute("kickstart", self.target)
        return f"Restarted {LABEL}."

    def status(self) -> str:
        self._ensure_platform()
        result = self._execute("print", self.target, check=False)
        if result.returncode != 0:
            raise LaunchAgentError(
                f"{LABEL} is not loaded. Start it with `uv run mlx-whisper-vocamac-agent start`."
            )
        return result.stdout.strip()

    def uninstall(self) -> str:
        self._ensure_platform()
        if self._is_loaded():
            self._execute("bootout", self.target)
        self.plist_path.unlink(missing_ok=True)
        return (
            f"Uninstalled {LABEL}. Operational logs and the Hugging Face model cache "
            "were left untouched."
        )

    def _ensure_platform(self) -> None:
        if self.platform_name != "darwin":
            raise LaunchAgentError("The per-user LaunchAgent is available only on macOS.")

    def _validate_install_prerequisites(self) -> None:
        self._ensure_platform()
        if not (self.checkout / "pyproject.toml").is_file():
            raise LaunchAgentError(f"Selected checkout is invalid: {self.checkout}")
        expected_venv = (self.checkout / ".venv").resolve()
        if self.python.parent.parent.resolve() != expected_venv:
            raise LaunchAgentError(
                "The selected Python executable must be the checkout's .venv/bin/python. "
                "Run `uv sync --group dev` and retry with `uv run "
                "mlx-whisper-vocamac-agent install`."
            )
        if not self.python.is_file() or not os.access(self.python, os.X_OK):
            raise LaunchAgentError(
                f"Python environment is missing at {self.python}; run `uv sync --group dev`."
            )
        if self.ffmpeg is None or not self.ffmpeg.is_file() or not os.access(self.ffmpeg, os.X_OK):
            raise LaunchAgentError(
                "FFmpeg was not found on PATH; install it with `brew install ffmpeg`, "
                "then rerun the LaunchAgent install command."
            )
        checkout = self.checkout.resolve()
        if self.log_dir.resolve().is_relative_to(checkout):
            raise LaunchAgentError("Operational logs must be stored outside the selected checkout.")
        if self.cache_dir.resolve().is_relative_to(checkout):
            raise LaunchAgentError(
                "The Hugging Face cache must be stored outside the selected checkout."
            )

    def _ensure_directories(self) -> None:
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.log_dir.chmod(0o700)

    def _plist(self) -> dict[str, Any]:
        if self.ffmpeg is None:
            raise LaunchAgentError("FFmpeg is required to generate the LaunchAgent configuration.")
        paths = dict.fromkeys((str(self.ffmpeg.parent), *SYSTEM_PATHS))
        return {
            "Label": LABEL,
            "ProgramArguments": [str(self.python), "-m", "mlx_whisper_vocamac.cli"],
            "WorkingDirectory": str(self.checkout),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": RESTART_THROTTLE_SECONDS,
            "Umask": 0o077,
            "StandardOutPath": str(self.log_dir / "service.log"),
            "StandardErrorPath": str(self.log_dir / "error.log"),
            "EnvironmentVariables": {
                "HF_HOME": str(self.cache_dir),
                "PATH": os.pathsep.join(paths),
                "PYTHONUNBUFFERED": "1",
            },
        }

    def _write_plist(self) -> None:
        contents = plistlib.dumps(self._plist(), fmt=plistlib.FMT_XML, sort_keys=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{PLIST_NAME}.", suffix=".tmp", dir=self.plist_path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(contents)
            temporary_path.chmod(0o600)
            temporary_path.replace(self.plist_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _is_loaded(self) -> bool:
        result = self._execute("print", self.target, check=False)
        if result.returncode == 0:
            return True
        detail = (result.stderr or result.stdout).strip()
        if "not found" in detail.lower() or "could not find" in detail.lower():
            return False
        raise LaunchAgentError(
            f"launchctl print {self.target} failed ({result.returncode})"
            f"{': ' + detail if detail else '.'}"
        )

    def _execute(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        command = [self.launchctl, *arguments]
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise LaunchAgentError(f"Could not run launchctl: {exc}") from exc
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise LaunchAgentError(
                f"launchctl {' '.join(arguments)} failed ({result.returncode})"
                f"{': ' + detail if detail else '.'}"
            )
        return result


def _manager_for_current_checkout() -> LaunchAgentManager:
    checkout = Path(__file__).resolve().parents[2]
    virtualenv = (checkout / ".venv").resolve()
    if Path(sys.prefix).resolve() != virtualenv:
        raise LaunchAgentError(
            "Run the agent command from the selected checkout's uv environment: "
            "`uv run mlx-whisper-vocamac-agent install`."
        )
    ffmpeg_name = shutil.which("ffmpeg")
    return LaunchAgentManager(
        checkout=checkout,
        python=checkout / ".venv" / "bin" / "python",
        ffmpeg=Path(ffmpeg_name) if ffmpeg_name else None,
        home=Path.home(),
        uid=os.getuid(),
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Install and manage the per-user macOS transcription LaunchAgent."
    )
    parser.add_argument(
        "action",
        choices=("install", "start", "stop", "restart", "status", "uninstall"),
        help="install also updates the plist and starts the service",
    )
    args = parser.parse_args(argv)
    try:
        manager = _manager_for_current_checkout()
        result = getattr(manager, args.action)()
    except LaunchAgentError as exc:
        parser.exit(1, f"error: {exc}\n")
    print(result)
