import asyncio
import logging
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from mlx_whisper_vocamac.app import (
    MODEL_ALIAS,
    MODEL_ID,
    MODEL_REVISION,
    create_app,
    transcribe_with_mlx,
)


def wav_upload(data: bytes = b"RIFF-test-audio") -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("dictation.wav", data, "audio/wav")}


def test_transcription_returns_openai_compatible_json_and_deletes_temp_audio() -> None:
    observed: dict[str, object] = {}

    def fake_transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, object]:
        observed.update(
            audio_path=audio_path,
            exists_during_call=audio_path.is_file(),
            mode_during_call=audio_path.stat().st_mode & 0o777,
            language=language,
            prompt=prompt,
        )
        return {"text": "The harbor lights are on, Elin."}

    client = TestClient(create_app(transcriber=fake_transcriber))
    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS, "language": "en", "prompt": "Elin"},
        files=wav_upload(),
    )

    assert response.status_code == 200
    assert response.json() == {"text": "The harbor lights are on, Elin."}
    assert observed["exists_during_call"] is True
    assert observed["language"] == "en"
    assert observed["prompt"] == "Elin"
    assert isinstance(observed["audio_path"], Path)
    assert observed["mode_during_call"] == 0o600
    assert not observed["audio_path"].exists()


def test_text_response_format_returns_plain_text() -> None:
    client = TestClient(create_app(transcriber=lambda *_args, **_kwargs: {"text": "hello"}))

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS, "response_format": "text"},
        files=wav_upload(),
    )

    assert response.status_code == 200
    assert response.text == "hello"
    assert response.headers["content-type"].startswith("text/plain")


def test_unknown_model_is_rejected_without_transcribing() -> None:
    client = TestClient(create_app(transcriber=lambda *_args, **_kwargs: pytest.fail()))

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": "not-the-local-model"},
        files=wav_upload(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_unsupported_format_is_rejected() -> None:
    client = TestClient(create_app(transcriber=lambda *_args, **_kwargs: pytest.fail()))

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS},
        files={"file": ("dictation.exe", b"not audio", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_audio"


def test_oversized_audio_is_rejected_before_backend_call() -> None:
    client = TestClient(
        create_app(
            transcriber=lambda *_args, **_kwargs: pytest.fail(),
            max_audio_bytes=4,
        )
    )

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS},
        files=wav_upload(b"12345"),
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_health_is_not_ready_until_a_transcription_succeeds() -> None:
    client = TestClient(create_app(transcriber=lambda *_args, **_kwargs: {"text": "ok"}))

    starting = client.get("/health")

    assert starting.status_code == 503
    assert starting.json() == {"status": "starting"}

    transcription = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS},
        files=wav_upload(),
    )

    assert transcription.status_code == 200
    assert client.get("/health").json() == {"status": "ready"}


def test_backend_error_does_not_expose_exception_text() -> None:
    def broken_transcriber(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("private audio path and transcript must not escape")

    client = TestClient(create_app(transcriber=broken_transcriber))
    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS},
        files=wav_upload(),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "backend_unavailable"
    assert "private audio" not in response.text


def test_oversized_multipart_request_is_rejected_before_parsing_the_file() -> None:
    client = TestClient(
        create_app(
            transcriber=lambda *_args, **_kwargs: pytest.fail(),
            max_audio_bytes=4,
        )
    )

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": MODEL_ALIAS},
        files={"file": ("dictation.exe", b"x" * (64 * 1024 + 1), "application/octet-stream")},
    )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "request_too_large"


def test_oversized_streaming_request_is_rejected_without_content_length() -> None:
    boundary = "streaming-boundary"
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"{MODEL_ALIAS}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="dictation.exe"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    suffix = f"\r\n--{boundary}--\r\n".encode()

    async def body():
        yield prefix
        yield b"x" * (64 * 1024 + 1)
        yield suffix

    async def submit() -> httpx.Response:
        transport = httpx.ASGITransport(
            app=create_app(
                transcriber=lambda *_args, **_kwargs: pytest.fail(),
                max_audio_bytes=4,
            )
        )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/audio/transcriptions",
                content=body(),
                headers={"content-type": f"multipart/form-data; boundary={boundary}"},
            )

    response = asyncio.run(submit())

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "request_too_large"


def test_malformed_multipart_is_rejected_without_calling_the_backend() -> None:
    client = TestClient(create_app(transcriber=lambda *_args, **_kwargs: pytest.fail()))

    response = client.post(
        "/v1/audio/transcriptions",
        content=b"--broken-boundary\r\nnot a valid multipart body",
        headers={"content-type": "multipart/form-data; boundary=broken-boundary"},
    )

    assert response.status_code == 400


def test_mlx_snapshot_startup_failure_can_recover_on_retry(monkeypatch) -> None:
    snapshot_calls = 0
    observed_download: dict[str, str] = {}
    observed_transcription: dict[str, object] = {}

    def snapshot_download(*, repo_id: str, revision: str) -> str:
        nonlocal snapshot_calls
        snapshot_calls += 1
        observed_download.update(repo_id=repo_id, revision=revision)
        if snapshot_calls == 1:
            raise OSError("temporary model snapshot failure")
        return "/external-model-cache/pinned-snapshot"

    def transcribe(audio_path: str, **options: object) -> dict[str, str]:
        observed_transcription.update(audio_path=audio_path, **options)
        return {"text": "ok"}

    mlx_module = ModuleType("mlx_whisper")
    mlx_module.transcribe = transcribe
    hub_module = ModuleType("huggingface_hub")
    hub_module.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "mlx_whisper", mlx_module)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_module)

    client = TestClient(create_app(transcriber=transcribe_with_mlx))
    with client:
        failed = client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files=wav_upload(),
        )
        health_after_failure = client.get("/health")
        recovered = client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files=wav_upload(),
        )

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "backend_unavailable"
    assert health_after_failure.json() == {"status": "starting"}
    assert recovered.status_code == 200
    assert recovered.json() == {"text": "ok"}
    assert client.get("/health").json() == {"status": "ready"}
    assert snapshot_calls == 2
    assert observed_download == {"repo_id": MODEL_ID, "revision": MODEL_REVISION}
    assert observed_transcription["path_or_hf_repo"] == "/external-model-cache/pinned-snapshot"


def test_malformed_audio_failure_recovers_and_does_not_log_request_data(caplog) -> None:
    audio_marker = b"private-audio-payload"
    transcript_marker = "private-transcript-content"
    observed_paths: list[Path] = []

    def transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, str]:
        observed_paths.append(audio_path)
        if audio_path.read_bytes() == audio_marker:
            raise ValueError(f"decode failed: {audio_marker!r}; {transcript_marker}")
        return {"text": transcript_marker}

    client = TestClient(create_app(transcriber=transcriber))
    with caplog.at_level(logging.ERROR, logger="mlx_whisper_vocamac.app"):
        failed = client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files={"file": ("private-name.wav", audio_marker, "audio/wav")},
        )
        health_after_failure = client.get("/health")
        recovered = client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files=wav_upload(),
        )
        failed_after_ready = client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files={"file": ("private-name.wav", audio_marker, "audio/wav")},
        )

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "backend_unavailable"
    assert health_after_failure.status_code == 503
    assert health_after_failure.json() == {"status": "starting"}
    assert recovered.status_code == 200
    assert recovered.json() == {"text": transcript_marker}
    assert client.get("/health").json() == {"status": "ready"}
    assert failed_after_ready.status_code == 503
    assert failed_after_ready.json()["error"]["code"] == "backend_unavailable"
    assert client.get("/health").json() == {"status": "ready"}
    assert len(observed_paths) == 3
    assert all(not path.exists() for path in observed_paths)
    assert "private-audio-payload" not in caplog.text
    assert "private-transcript-content" not in caplog.text
    assert "private-name.wav" not in caplog.text


def test_repeated_requests_use_and_remove_distinct_temporary_files() -> None:
    observed_paths: list[Path] = []

    def transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, str]:
        observed_paths.append(audio_path)
        return {"text": "ok"}

    client = TestClient(create_app(transcriber=transcriber))

    responses = [
        client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files=wav_upload(bytes([index]) * 8),
        )
        for index in range(3)
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert len(observed_paths) == 3
    assert len(set(observed_paths)) == 3
    assert all(not path.exists() for path in observed_paths)


def test_concurrent_requests_do_not_run_the_backend_in_parallel() -> None:
    state_lock = threading.Lock()
    active_calls = 0
    maximum_active_calls = 0
    observed_paths: list[Path] = []

    def transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, str]:
        nonlocal active_calls, maximum_active_calls
        with state_lock:
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
            observed_paths.append(audio_path)
        time.sleep(0.05)
        with state_lock:
            active_calls -= 1
        return {"text": "ok"}

    client = TestClient(create_app(transcriber=transcriber))

    def submit(index: int) -> httpx.Response:
        return client.post(
            "/v1/audio/transcriptions",
            data={"model": MODEL_ALIAS},
            files=wav_upload(bytes([index]) * 8),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert maximum_active_calls == 1
    assert len(observed_paths) == 2
    assert all(not path.exists() for path in observed_paths)


def test_cancelled_client_request_keeps_audio_until_backend_finishes_then_cleans_it() -> None:
    backend_started = threading.Event()
    release_backend = threading.Event()
    observed_paths: list[Path] = []

    def transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, str]:
        observed_paths.append(audio_path)
        backend_started.set()
        if not release_backend.wait(timeout=5):
            raise TimeoutError("test backend was not released")
        return {"text": "ok"}

    async def exercise_disconnect() -> None:
        transport = httpx.ASGITransport(app=create_app(transcriber=transcriber))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            request = asyncio.create_task(
                client.post(
                    "/v1/audio/transcriptions",
                    data={"model": MODEL_ALIAS},
                    files=wav_upload(),
                )
            )
            for _ in range(200):
                if backend_started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert backend_started.is_set()
            assert len(observed_paths) == 1
            request.cancel()
            await asyncio.sleep(0.02)
            assert observed_paths[0].is_file()
            release_backend.set()
            with pytest.raises(asyncio.CancelledError):
                await request

    try:
        asyncio.run(exercise_disconnect())
    finally:
        release_backend.set()

    assert len(observed_paths) == 1
    assert not observed_paths[0].exists()


def test_socket_disconnect_keeps_audio_until_backend_finishes_then_cleans_it() -> None:
    backend_started = threading.Event()
    release_backend = threading.Event()
    backend_finished = threading.Event()
    observed_paths: list[Path] = []

    def transcriber(
        audio_path: Path, *, language: str | None, prompt: str | None
    ) -> dict[str, str]:
        observed_paths.append(audio_path)
        backend_started.set()
        if not release_backend.wait(timeout=5):
            raise TimeoutError("test backend was not released")
        backend_finished.set()
        return {"text": "ok"}

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(transcriber=transcriber),
            log_level="critical",
            access_log=False,
            lifespan="off",
        )
    )
    server_thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    client_socket: socket.socket | None = None
    server_thread.start()

    try:
        startup_deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < startup_deadline:
            time.sleep(0.01)
        assert server.started

        boundary = b"disconnect-test-boundary"
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="model"\r\n\r\n'
            b"transcription-default\r\n"
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="sample.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n"
            b"RIFFsynthetic-audio"
            b"\r\n--" + boundary + b"--\r\n"
        )
        client_socket = socket.create_connection(("127.0.0.1", port), timeout=5)
        client_socket.sendall(
            b"POST /v1/audio/transcriptions HTTP/1.1\r\n"
            + f"Host: 127.0.0.1:{port}\r\n".encode()
            + b"Connection: close\r\n"
            + b"Content-Type: multipart/form-data; boundary="
            + boundary
            + b"\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )

        assert backend_started.wait(timeout=5)
        assert len(observed_paths) == 1
        assert observed_paths[0].is_file()
        client_socket.close()
        client_socket = None
        assert observed_paths[0].is_file()

        release_backend.set()
        assert backend_finished.wait(timeout=5)
        cleanup_deadline = time.monotonic() + 5
        while observed_paths[0].exists() and time.monotonic() < cleanup_deadline:
            time.sleep(0.01)
        assert not observed_paths[0].exists()
    finally:
        release_backend.set()
        if client_socket is not None:
            client_socket.close()
        server.should_exit = True
        server_thread.join(timeout=5)
        listener.close()

    assert not server_thread.is_alive()
