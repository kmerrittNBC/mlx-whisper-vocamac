from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-dev.sh"


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def installer_environment(
    tmp_path: Path,
    *,
    architecture: str = "arm64",
    macos_version: str = "14.0",
    port_busy: bool = False,
    job_loaded: bool = False,
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "commands.log"
    app_path = tmp_path / "Applications" / "VocaMac.app"

    write_executable(
        bin_dir / "uname",
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  -s) printf "Darwin\\n" ;;\n'
        '  -m) printf "%s\\n" "$FAKE_ARCH" ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n",
    )
    write_executable(
        bin_dir / "sw_vers",
        "#!/bin/sh\n"
        'test "$1" = "-productVersion" || exit 2\n'
        'printf "%s\\n" "$FAKE_MACOS_VERSION"\n',
    )
    write_executable(
        bin_dir / "launchctl",
        '#!/bin/sh\nif [ "$1" = print ] && [ "$FAKE_JOB_LOADED" = 1 ]; then exit 0; fi\nexit 113\n',
    )
    write_executable(
        bin_dir / "lsof",
        "#!/bin/sh\n"
        'if [ "$FAKE_PORT_BUSY" = 1 ]; then\n'
        '  printf "node 123 user 4u IPv4 TCP *:8765 (LISTEN)\\n"\n'
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
    )
    write_executable(
        bin_dir / "brew",
        "#!/bin/sh\n"
        'printf "brew %s\\n" "$*" >> "$INSTALLER_LOG"\n'
        'if [ "$1" = install ] && [ "$2" = --cask ]; then\n'
        '  mkdir -p "$VOCAMAC_APP_PATH/Contents"\n'
        "  cat > \"$VOCAMAC_APP_PATH/Contents/Info.plist\" <<'PLIST'\n"
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        "<key>CFBundleShortVersionString</key><string>1.2.0</string>\n"
        "</dict></plist>\n"
        "PLIST\n"
        "fi\n",
    )
    for command in ("uv", "open"):
        write_executable(
            bin_dir / command,
            f'#!/bin/sh\nprintf "{command} %s\\n" "$*" >> "$INSTALLER_LOG"\n',
        )

    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        HOME=str(home),
        INSTALLER_LOG=str(log),
        VOCAMAC_APP_PATH=str(app_path),
        FAKE_ARCH=architecture,
        FAKE_MACOS_VERSION=macos_version,
        FAKE_PORT_BUSY="1" if port_busy else "0",
        FAKE_JOB_LOADED="1" if job_loaded else "0",
    )
    return env, log


def copy_installer_to_primary_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    scripts = checkout / "scripts"
    scripts.mkdir()
    installer = scripts / "install-dev.sh"
    shutil.copy2(INSTALLER, installer)
    return installer


def run_installer(env: dict[str, str], installer: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(installer), "--yes"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_clean_setup_installs_vocamac_and_service_then_opens_the_app(tmp_path: Path) -> None:
    env, log = installer_environment(tmp_path)
    installer = copy_installer_to_primary_checkout(tmp_path)

    result = run_installer(env, installer)

    assert result.returncode == 0, result.stderr
    commands = log.read_text().splitlines()
    assert commands == [
        "brew install uv ffmpeg",
        "brew tap vocahq/vocamac",
        "brew trust vocahq/vocamac",
        "brew install --cask vocamac",
        "uv sync --group dev",
        "uv run mlx-whisper-vocamac-agent install",
        f"open -a {env['VOCAMAC_APP_PATH']}",
    ]
    assert "Settings → Speech Model → Custom Endpoint" in result.stdout
    assert "http://127.0.0.1:8765" in result.stdout


def test_existing_vocamac_install_is_reused_without_reinstalling_the_cask(
    tmp_path: Path,
) -> None:
    env, log = installer_environment(tmp_path)
    app_path = Path(env["VOCAMAC_APP_PATH"])
    installer = copy_installer_to_primary_checkout(tmp_path)
    app_path.joinpath("Contents").mkdir(parents=True)
    app_path.joinpath("Contents", "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "1.2.0"})
    )

    result = run_installer(env, installer)

    assert result.returncode == 0, result.stderr
    commands = log.read_text().splitlines()
    assert "brew tap vocahq/vocamac" not in commands
    assert "brew trust vocahq/vocamac" not in commands
    assert "brew install --cask vocamac" not in commands
    assert "uv run mlx-whisper-vocamac-agent install" in commands
    assert f"open -a {app_path}" in commands


def test_port_collision_stops_before_installing_or_starting_services(tmp_path: Path) -> None:
    env, log = installer_environment(tmp_path, port_busy=True)
    installer = copy_installer_to_primary_checkout(tmp_path)

    result = run_installer(env, installer)

    assert result.returncode != 0
    assert "8765" in result.stderr
    assert "node 123" in result.stderr
    assert not log.exists()


def test_unsupported_architecture_stops_before_running_brew(tmp_path: Path) -> None:
    env, log = installer_environment(tmp_path, architecture="x86_64")
    installer = copy_installer_to_primary_checkout(tmp_path)

    result = run_installer(env, installer)

    assert result.returncode != 0
    assert "Apple Silicon" in result.stderr
    assert not log.exists()


def test_linked_worktree_is_refused_to_keep_launchagent_path_persistent(
    tmp_path: Path,
) -> None:
    env, log = installer_environment(tmp_path)

    result = run_installer(env, INSTALLER)

    assert result.returncode != 0
    assert "persistent checkout" in result.stderr
    assert not log.exists()
