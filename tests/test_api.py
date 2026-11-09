from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mlx_whisper_vocamac.app import MODEL_ALIAS, create_app


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
