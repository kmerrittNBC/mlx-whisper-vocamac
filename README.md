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

The API starts on `http://127.0.0.1:8000`. The first dictation downloads the pinned
model (about 1.6 GB) and loads it; later requests reuse the local cache. Audio is
held in a request-scoped temporary file while FFmpeg/MLX reads it, and that file is
removed after the request. Transcripts and audio are not logged.

## Configure VocaMac

In **Settings → Speech Model → Custom Endpoint**, select **OpenAI-compatible** and
set:

| Setting | Value |
| --- | --- |
| Base URL | `http://127.0.0.1:8000` |
| Model | `transcription-default` |
| API key | Leave blank |

VocaMac sends WAV audio to `/v1/audio/transcriptions`. This server is intentionally
loopback-only and has no authentication; do not put it behind a network-facing
reverse proxy or change its bind address without adding an authentication boundary.

## Verify it

Health is `starting` until one request has loaded and successfully used the model:

```sh
curl -i http://127.0.0.1:8000/health
```

Send a local recording:

```sh
curl -sS http://127.0.0.1:8000/v1/audio/transcriptions \
  -F model=transcription-default \
  -F file=@recording.wav
```

Successful default responses are OpenAI-compatible JSON: `{"text":"..."}`. The
service also accepts `response_format=text` and `response_format=verbose_json`, plus
optional `language` and `prompt` fields. The prompt is passed to Whisper as an
initial vocabulary/context hint, not as transcript text.

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
