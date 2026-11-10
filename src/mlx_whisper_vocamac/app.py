from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

MODEL_ALIAS = "transcription-default"
MODEL_ID = "mlx-community/whisper-large-v3-turbo"
MODEL_REVISION = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 500
SUPPORTED_AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".mp4", ".ogg", ".wav", ".webm"}

Transcriber = Callable[..., dict[str, Any]]
logger = logging.getLogger(__name__)


class RequestBodyTooLarge(HTTPException):
    """The encoded multipart request exceeds the bounded upload size."""

    def __init__(self) -> None:
        super().__init__(
            status_code=413,
            detail="The request exceeds the upload size limit.",
        )


class UploadRequestLimitMiddleware:
    """Bound the request body before Starlette spools multipart uploads to disk."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/v1/audio/transcriptions"
        ):
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value
                for name, value in scope.get("headers", ())
                if name.lower() == b"content-length"
            ),
            None,
        )
        try:
            declared_length = int(content_length) if content_length is not None else None
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > self.max_bytes:
            await _request_too_large_response()(scope, receive, send)
            return

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise RequestBodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


def transcribe_with_mlx(
    audio_path: Path, *, language: str | None, prompt: str | None
) -> dict[str, Any]:
    """Run the pinned MLX checkpoint, downloading it to the external HF cache if needed."""
    import mlx_whisper
    from huggingface_hub import snapshot_download

    model_path = snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION)
    options: dict[str, Any] = {
        "path_or_hf_repo": model_path,
        "temperature": 0.0,
        "verbose": None,
    }
    if language:
        options["language"] = language.split("-", maxsplit=1)[0].lower()
    if prompt:
        options["initial_prompt"] = prompt
    return mlx_whisper.transcribe(str(audio_path), **options)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": "invalid_request_error", "code": code}},
    )


def _request_too_large_response() -> JSONResponse:
    return _error(
        413,
        "request_too_large",
        "The request exceeds the upload size limit.",
    )


def _verbose_response(result: dict[str, Any]) -> dict[str, Any]:
    segments = [
        {
            "id": int(segment.get("id", index)),
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "text": str(segment.get("text", "")),
        }
        for index, segment in enumerate(result.get("segments", []))
    ]
    return {
        "text": str(result.get("text", "")),
        "language": result.get("language"),
        "duration": max((segment["end"] for segment in segments), default=0.0),
        "segments": segments,
        "words": None,
    }


def create_app(
    *,
    transcriber: Transcriber = transcribe_with_mlx,
    max_audio_bytes: int = MAX_AUDIO_BYTES,
) -> FastAPI:
    app = FastAPI(title="MLX Whisper for VocaMac", docs_url=None, redoc_url=None)
    app.add_middleware(
        UploadRequestLimitMiddleware,
        max_bytes=max_audio_bytes + MAX_MULTIPART_OVERHEAD_BYTES,
    )
    inference_lock = Lock()
    app.state.model_ready = False

    @app.exception_handler(RequestBodyTooLarge)
    async def request_body_too_large(_request: Request, _exc: RequestBodyTooLarge) -> JSONResponse:
        return _request_too_large_response()

    @app.get("/health")
    async def health() -> Response:
        if app.state.model_ready:
            return JSONResponse({"status": "ready"})
        return JSONResponse(status_code=503, content={"status": "starting"})

    @app.post("/v1/audio/transcriptions")
    async def transcriptions(
        file: Annotated[UploadFile | None, File()] = None,
        model: Annotated[str | None, Form()] = None,
        language: Annotated[str | None, Form()] = None,
        prompt: Annotated[str | None, Form()] = None,
        response_format: Annotated[str, Form()] = "json",
    ) -> Response:
        if model is None:
            return _error(400, "missing_field", "The model field is required.")
        if model != MODEL_ALIAS:
            return _error(404, "model_not_found", "The requested model is not served.")
        if file is None:
            return _error(400, "missing_field", "The file field is required.")
        if response_format not in {"json", "text", "verbose_json"}:
            return _error(400, "invalid_field", "Unsupported response format.")
        if language is not None and not re.fullmatch(r"[A-Za-z]{2}(?:-[A-Za-z]{2})?", language):
            return _error(400, "invalid_field", "Language must be an ISO 639-1 code.")
        if prompt is not None and len(prompt) > MAX_PROMPT_CHARS:
            return _error(400, "invalid_field", "The prompt is too long.")

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in SUPPORTED_AUDIO_SUFFIXES:
            await file.close()
            return _error(400, "unsupported_audio", "The uploaded audio format is not supported.")

        try:
            audio_bytes = await file.read(max_audio_bytes + 1)
        finally:
            await file.close()

        if not audio_bytes:
            return _error(400, "empty_audio", "The uploaded audio file is empty.")
        if len(audio_bytes) > max_audio_bytes:
            return _error(413, "file_too_large", "The uploaded audio file exceeds the size limit.")

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=suffix, prefix="mlx-whisper-", delete=False
            ) as audio_file:
                audio_file.write(audio_bytes)
                temp_path = Path(audio_file.name)

            def run_inference() -> dict[str, Any]:
                with inference_lock:
                    return transcriber(temp_path, language=language, prompt=prompt)

            inference_task = asyncio.create_task(run_in_threadpool(run_inference))
            try:
                result = await asyncio.shield(inference_task)
            except asyncio.CancelledError:
                try:
                    await inference_task
                except Exception:
                    pass
                raise
            text = result.get("text")
            if not isinstance(text, str):
                raise ValueError("The transcription backend returned no text.")
            app.state.model_ready = True
        except Exception as exc:
            logger.error("transcription backend failed (%s)", type(exc).__name__)
            return _error(
                503,
                "backend_unavailable",
                "The local transcription model is unavailable.",
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        if response_format == "text":
            return PlainTextResponse(text)
        if response_format == "verbose_json":
            return JSONResponse(_verbose_response(result))
        return JSONResponse({"text": text})

    return app


app = create_app()
