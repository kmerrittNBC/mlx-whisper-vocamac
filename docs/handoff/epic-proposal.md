# Gitea handoff: local MLX Whisper dictation

## Repository and current state

- Gitea: <https://tea.kyle-merritt.com/anodyine/mlx-whisper-vocamac>
- GitHub: <https://github.com/kmerrittNBC/mlx-whisper-vocamac>
- Default branch: `main`; both remotes currently contain commit
  `989b8ddb71066df8662ffa8bc13081253d0b1d9a`.
- The service is a macOS Apple Silicon project. A Linux machine can manage the
  Gitea issues, but cannot run its MLX inference service.
- `make check` passes (7 provider-free API tests). These use a fake
  transcriber; they do not prove the real weights or microphone flow works.
- The pinned checkpoint is
  `mlx-community/whisper-large-v3-turbo` at revision
  `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`. It is the MLX conversion of the
  same large-v3-turbo variant as the earlier helper-server candidate, not its
  CTranslate2 artifact.
- A first live smoke attempt has **not** completed. `say` produced an AIFF,
  but conversion failed because `ffmpeg` was not installed; consequently the
  WAV file was missing and `curl` never submitted a transcription. Install
  FFmpeg on the Mac with `brew install ffmpeg`, then follow the README.
- The first successful transcription downloads and loads the pinned model into
  the external Hugging Face cache. Model weights and recordings are not checked
  into Git.

## Proposed epic

**Title:** Deliver local MLX Whisper dictation on macOS

**Problem**

This repository has a loopback-only OpenAI-compatible endpoint for VocaMac,
but it has not yet been verified with the actual MLX checkpoint or a real
VocaMac dictation session on the target Mac.

**Scope**

Make installation and local dictation reproducible on the Apple Silicon Mac,
verify the pinned Whisper large-v3-turbo model through VocaMac's Custom
Endpoint, and document measured behavior and operational limits. Keep the
service loopback-only; LAN access, speech synthesis, and model training are
out of scope.

**Acceptance criteria**

- A clean setup on the target Mac installs the pinned Python dependencies and
  completes a real transcription using the pinned MLX model revision.
- VocaMac can submit a recording to the local endpoint and insert the returned
  transcript into the active text field.
- The owner verifies silence and ordinary dictation, records latency and
  recognition observations, and reviews any errors before setting acceptance
  thresholds.
- The service remains bound to loopback, enforces its request-size limit,
  removes request-scoped temporary audio, and does not log audio or transcript
  contents.
- Installation, first-run model download, troubleshooting, and the tested
  VocaMac settings are documented.

Create the epic first, then its child issues. Once the children have Gitea
issue numbers, add them to the epic under `## Child Issues In Priority Order`
in the order below and place the epic in the repository's top-level work queue.

## Proposed child issues, in priority order

### 1. Run the pinned MLX Whisper model end to end on the M5 Pro

**Problem:** Provider-free tests do not establish that the real model loads,
downloads to the external cache, decodes audio, or runs acceptably on the
target Mac.

**Scope:** Follow the documented install, install FFmpeg, start the service,
and perform a real transcription using the pinned model revision. Record the
runtime versions and cold/warm timing without retaining private audio or
transcript text in Git.

**Acceptance criteria:** A real local WAV transcription succeeds; the health
endpoint transitions from `starting` to `ready`; the model cache is outside
the repository; cold-start and warm-request timings are recorded.

### 2. Verify VocaMac Custom Endpoint dictation and text insertion

**Problem:** An HTTP smoke request does not verify microphone capture,
VocaMac's Custom Endpoint settings, or insertion at the active cursor.

**Scope:** Configure VocaMac's OpenAI-compatible Custom Endpoint to use
`http://127.0.0.1:8000` and model `transcription-default`. Verify push-to-talk,
ordinary speech, silence, and insertion into more than one text field.

**Acceptance criteria:** Dictated words are inserted at the intended cursor;
silence does not insert stray text; endpoint and model settings are recorded;
any app permission or usability issue is captured without including private
recordings or transcripts.

### 3. Harden the local service for dictation failures and privacy

**Problem:** The initial API tests cover the basic contract but do not yet
establish real-backend recovery, client cancellation behavior, or all relevant
failure modes.

**Scope:** Review and test upload bounds, unsupported and malformed media,
backend startup/failure responses, repeated requests, concurrent requests, and
client disconnect behavior. Keep the API loopback-only and ensure request data
is not logged or retained.

**Acceptance criteria:** Focused tests cover each agreed failure case; service
health and recovery behavior are documented; tests confirm temporary-file
cleanup; no request audio or transcript appears in logs or Git.

### 4. Finish the install, troubleshooting, and acceptance guide

**Problem:** The README has a starter quickstart, but the first attempted smoke
test exposed that the FFmpeg prerequisite and missing-WAV follow-on failure
need to be unmistakable.

**Scope:** Document prerequisites, clean installation, first model download,
two-terminal server/smoke workflow, VocaMac configuration, expected health
states, common setup errors, and how to stop the server. Keep all test audio
outside the repository.

**Acceptance criteria:** A second operator can follow the guide from a clean
Apple Silicon macOS setup and complete both an HTTP smoke test and VocaMac
dictation without relying on undocumented steps.

## Issue-workflow setup note

If the repository will use the bundled Gitea queue helpers, initialize the
standard labels and canonical roadmap before placing work. Run `labels setup`
and `queue init` with the Gitea helper installed on that machine; the helper
path and credentials are machine-local, so do not copy credentials into this
repository. From the Gitea UI, ensure the roadmap and epic/child labels follow
the same queue convention. Then create the epic and children, attach the
children in the order above, and insert the epic into the roadmap. Keep the
issue titles and acceptance criteria aligned with this handoff as the work is
refined.
