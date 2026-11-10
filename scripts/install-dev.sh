#!/bin/sh
set -eu

LABEL="com.anodyine.mlx-whisper-vocamac"
PORT=8765
APP_PATH=${VOCAMAC_APP_PATH:-}
ASSUME_YES=0

usage() {
    cat <<'EOF'
Install developer prerequisites, VocaMac, and this checkout's local service.

Usage: ./scripts/install-dev.sh [--yes]

The installer asks before trusting VocaMac's third-party Homebrew tap. --yes
accepts that trust step non-interactively. The script never writes VocaMac's
private endpoint preferences or grants macOS privacy permissions.
EOF
}

fail() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes) ASSUME_YES=1 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; fail "unknown option: $1" ;;
    esac
    shift
done

[ "$(uname -s)" = "Darwin" ] || fail "VocaMac setup requires macOS."
[ "$(uname -m)" = "arm64" ] || fail "VocaMac setup requires an Apple Silicon Mac (arm64)."

macos_major=$(sw_vers -productVersion | awk -F. 'NR == 1 { print $1 }')
case "$macos_major" in
    ''|*[!0-9]*) fail "Could not determine the macOS version with sw_vers." ;;
esac
[ "$macos_major" -ge 14 ] || fail "VocaMac requires macOS 14 Sonoma or later."

command -v brew >/dev/null 2>&1 || fail "Homebrew is required; install it from https://brew.sh/ and rerun this script."
command -v launchctl >/dev/null 2>&1 || fail "launchctl is unavailable in this macOS session."
command -v lsof >/dev/null 2>&1 || fail "lsof is required to check whether port $PORT is occupied."

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd "$script_dir/.." && pwd)
if [ -f "$repo_root/.git" ]; then
    fail "This is a linked worktree. Run the installer from a persistent checkout (the primary clone) so future LaunchAgent starts do not depend on a removable worktree."
fi
cd "$repo_root"

gui_domain="gui/$(id -u)"
if ! launchctl print "$gui_domain/$LABEL" >/dev/null 2>&1 \
    && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    printf 'TCP port %s already has a listener:\n' "$PORT" >&2
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
    fail "Resolve the port conflict before installing the LaunchAgent."
fi

if [ -z "$APP_PATH" ]; then
    if [ -d /Applications/VocaMac.app ]; then
        APP_PATH=/Applications/VocaMac.app
    elif [ -d "$HOME/Applications/VocaMac.app" ]; then
        APP_PATH=$HOME/Applications/VocaMac.app
    else
        APP_PATH=/Applications/VocaMac.app
    fi
fi

if [ ! -d "$APP_PATH" ]; then
    if [ "$ASSUME_YES" -ne 1 ]; then
        if [ ! -t 0 ] || [ ! -r /dev/tty ]; then
            fail "Trusting vocahq/vocamac requires an interactive confirmation; rerun in Terminal or explicitly pass --yes."
        fi
        printf 'Trust the third-party Homebrew tap vocahq/vocamac to install VocaMac? [y/N] ' >&2
        IFS= read -r answer < /dev/tty || fail "Could not read the Homebrew trust confirmation."
        case "$answer" in
            y|Y|yes|YES|Yes) ;;
            *) fail "Homebrew tap trust was declined; VocaMac was not installed." ;;
        esac
    fi
    brew tap vocahq/vocamac
    brew trust vocahq/vocamac
    brew install --cask vocamac
fi

brew install uv ffmpeg

plist_buddy=/usr/libexec/PlistBuddy
[ -x "$plist_buddy" ] || fail "Could not verify VocaMac's version with $plist_buddy."
voca_version=$(
    "$plist_buddy" -c 'Print :CFBundleShortVersionString' "$APP_PATH/Contents/Info.plist" 2>/dev/null \
        || true
)
[ -n "$voca_version" ] || fail "Could not read the version from $APP_PATH."
if ! printf '%s\n' "$voca_version" | awk -F. '
    NF >= 2 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
        if ($1 + 0 > 1 || ($1 + 0 == 1 && $2 + 0 >= 1)) exit 0
    }
    { exit 1 }
'; then
    fail "VocaMac $voca_version is too old; upgrade it with 'brew upgrade --cask vocamac' or install VocaMac 1.1 or later, then rerun this script."
fi

uv sync --group dev
uv run mlx-whisper-vocamac-agent install
open -a "$APP_PATH"

cat <<'EOF'

VocaMac and the local transcription service are installed. Finish setup in VocaMac:

1. Grant Microphone, Input Monitoring, and Accessibility in System Settings if asked.
2. On the Language & Model screen, choose Set up later; do not download Fast English dictation.
3. Keep Push to Talk selected. The developer guide recommends Left Option + F3 (⌥F3).
4. On Ready to go, turn on Launch at Login.
5. Open Settings → Speech Model → Custom Endpoint and choose OpenAI-compatible.
6. Set Base URL to http://127.0.0.1:8765, Model to transcription-default, and leave API key blank.

The endpoint and macOS permissions are intentionally left for you to confirm in the UI.
The local model is downloaded to ~/.cache/huggingface on its first transcription.
EOF
