# MLX Whisper for VocaMac

A small, local OpenAI-compatible transcription service for [VocaMac](https://vocamac.com/),
using the MLX conversion of Whisper large-v3-turbo on Apple Silicon. It binds only to
`127.0.0.1`; it is not a LAN service.

The pinned model is `mlx-community/whisper-large-v3-turbo` at revision
`a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`. It is the same large-v3-turbo model
variant used as the first STT candidate in
[`multi-model-helper-server`](https://tea.kyle-merritt.com/anodyine/multi-model-helper-server),
but it is a separate MLX conversion rather than the CTranslate2 artifact used there.
The checkpoint is downloaded on first transcription into Hugging Face's external
cache; model weights and audio recordings do not belong in this repository.

## Requirements

- Apple Silicon Mac (tested target: M5 Pro, 48 GB unified memory)
- macOS 14 or later
- Python 3.13 (selected because MLX's native package support is tied to supported
  CPython builds; this project intentionally excludes Python 3.14+)
- [uv](https://docs.astral.sh/uv/) and [FFmpeg](https://ffmpeg.org/)
- VocaMac 1.1 or later for its Custom Endpoint setting

Install the system tools and Python environment:

```sh
brew install uv ffmpeg
uv sync --group dev
```

Start the service:

```sh
uv run mlx-whisper-vocamac
```

The API starts on `http://127.0.0.1:8765`. The first dictation downloads the pinned
model (about 1.6 GB) and loads it; later requests reuse the local cache. Audio is
held in a request-scoped temporary file while FFmpeg/MLX reads it, and that file is
removed after processing. Audio uploads are limited to 25 MiB, with up to 64 KiB
for multipart framing and form fields. Transcripts and audio are not logged.

## Start automatically at login

From the checkout you want the service to use, install or update its per-user
LaunchAgent:

```sh
uv run mlx-whisper-vocamac-agent install
```

This operation is safe to repeat. It creates or updates
`~/Library/LaunchAgents/com.anodyine.mlx-whisper-vocamac.plist`, registers and
starts the service immediately, and starts it at future logins. It does not use
`sudo` or install a system LaunchDaemon. The plist runs that checkout's
`.venv/bin/python` with the checkout as its working directory. Before changing
the LaunchAgent, the command checks that the selected Python environment and
FFmpeg are available and reports setup instructions if either is missing. Run
`uv sync --group dev` after changing dependencies, then repeat the install
command to update the registered job. There is one service per macOS user; if
you install from another checkout, that checkout replaces the service's source
path.

Run the following commands from the same checkout. `start` and `restart` load
the LaunchAgent if it is currently stopped; `stop` unloads it for the current
login session, while leaving it configured to start at the next login.

```sh
uv run mlx-whisper-vocamac-agent start
uv run mlx-whisper-vocamac-agent stop
uv run mlx-whisper-vocamac-agent restart
uv run mlx-whisper-vocamac-agent status
uv run mlx-whisper-vocamac-agent uninstall
```

`status` prints the `launchctl` job details and exits with an error if the job is
not loaded. `uninstall` unloads the job and removes only its plist; operational
logs and downloaded model files are preserved. If the service exits
unexpectedly, launchd restarts it and applies a 30-second restart throttle to
avoid a rapid restart loop. `restart` forces an immediate restart when manual
recovery is needed. Inspect these files when diagnosing startup failures:

- `~/Library/Logs/mlx-whisper-vocamac/service.log`
- `~/Library/Logs/mlx-whisper-vocamac/error.log`

The LaunchAgent writes logs with user-only file permissions. It does not enable
HTTP access logging, and the service does not log submitted audio or transcript
text. The model cache is kept at
`~/.cache/huggingface`, the standard Hugging Face cache location, outside the
checkout, and is not removed by `uninstall`.

The service does not warm the model at login. `/health` remains `starting`
until the first transcription successfully loads and uses the model; a missing
model is downloaded to the external cache on that first request.

To verify automatic login startup, install the agent, log out and back in (or
restart macOS), then run `uv run mlx-whisper-vocamac-agent status` from the same
checkout. Confirm that `/health` is `starting` before the first transcription.
The following macOS-only smoke test synthesizes disposable speech outside the
checkout, discards the response body, and checks that the endpoint succeeds and
then becomes ready. Confirm the default API port is not already occupied with
`lsof -nP -iTCP:8765 -sTCP:LISTEN`; if another process owns it, resolve that
conflict before starting this service.

```sh
set -eu
test_dir="$(mktemp -d "${TMPDIR:-/tmp}/mlx-whisper-agent-check.XXXXXX")"
trap 'rm -rf "$test_dir"' EXIT
curl --silent --show-error --include http://127.0.0.1:8765/health
say -o "$test_dir/sample.aiff" "The local transcription service is running."
ffmpeg -hide_banner -loglevel error -y -i "$test_dir/sample.aiff" \
  -ar 16000 -ac 1 "$test_dir/sample.wav"
curl --fail --silent --show-error --output /dev/null --write-out 'HTTP %{http_code}\n' \
  http://127.0.0.1:8765/v1/audio/transcriptions \
  -F model=transcription-default -F "file=@$test_dir/sample.wav"
curl --silent --show-error http://127.0.0.1:8765/health
```

Expected: `status` reports the loaded LaunchAgent; the initial health response
is HTTP 503 with `{"status":"starting"}`; the transcription request prints
`HTTP 200`; the final health response is `{"status":"ready"}`. Record
the observed job state and HTTP result in the implementation PR or issue, not
in a repository evidence file. Do not retain or commit a real recording or
transcript.

## Configure VocaMac

In **Settings → Speech Model → Custom Endpoint**, select **OpenAI-compatible** and
set:

| Setting | Value |
| --- | --- |
| Base URL | `http://127.0.0.1:8765` |
| Model | `transcription-default` |
| API key | Leave blank |

VocaMac sends WAV audio to `/v1/audio/transcriptions`. This server is intentionally
loopback-only and has no authentication; do not put it behind a network-facing
reverse proxy or change its bind address without adding an authentication boundary.

## Verify it

Health is `starting` until one request has loaded and successfully used the model:

```sh
curl -i http://127.0.0.1:8765/health
```

Send a local recording:

```sh
curl -sS http://127.0.0.1:8765/v1/audio/transcriptions \
  -F model=transcription-default \
  -F file=@recording.wav
```

Successful default responses are OpenAI-compatible JSON: `{"text":"..."}`. The
service also accepts `response_format=text` and `response_format=verbose_json`, plus
optional `language` and `prompt` fields. The prompt is passed to Whisper as an
initial vocabulary/context hint, not as transcript text.

## Failure, recovery, and privacy

`/health` reports `starting` until a transcription succeeds in the current
process. A failed model startup or inference returns HTTP 503 with the generic
`backend_unavailable` error and leaves health at `starting`; retry after
resolving a persistent backend problem. After one successful transcription,
health stays `ready` even if an individual later request fails. Unsupported
filename extensions and malformed multipart requests return HTTP 400. A
supported filename whose contents cannot be decoded may reach the backend and
return the same generic HTTP 503 response. Requests above the upload limit
return HTTP 413. The service rejects encoded request bodies larger than 25 MiB
plus 64 KiB before multipart parsing, including streaming requests without a
`Content-Length` header; an audio payload just over 25 MiB is rejected after
bounded multipart parsing.

Inference is serialized: concurrent dictations wait rather than using the MLX
backend in parallel. Disconnecting or canceling a client does not interrupt an
in-progress model call. The service keeps that request's temporary audio file
until the backend finishes, then removes it; a disconnected client receives no
result and can retry afterward. The HTTP access log is disabled, and backend
failures log only the exception type—not the exception message, audio, filename,
or transcript. Do not enable request-body or transcription logging in a proxy or
server added in front of this loopback-only service.

## Development

```sh
make check
```

The tests inject a fake transcriber and do not download or run model weights. A
real dictation check is still needed on the target Mac to assess latency, audio
format handling, and recognition quality with the owner's microphone and vocabulary.

## Model and code licensing

This repository's code is MIT-licensed. Model weights are not included; review the
model card and its upstream license before redistribution or other use. VocaMac is
separately licensed by its publisher.
