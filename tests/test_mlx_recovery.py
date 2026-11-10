import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mlx_whisper_vocamac.app import MODEL_ALIAS, MODEL_ID, MODEL_REVISION, create_app


def test_real_mlx_backend_recovers_after_malformed_audio() -> None:
    if os.environ.get("MLX_WHISPER_INTEGRATION") != "1":
        pytest.skip("set MLX_WHISPER_INTEGRATION=1 to run the cached-model integration test")
    if sys.platform != "darwin" or platform.machine() != "arm64":
        pytest.skip("the real MLX integration test requires Apple Silicon macOS")
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        pytest.skip("the real MLX integration test requires say and FFmpeg")

    from huggingface_hub import try_to_load_from_cache

    cached_weights = try_to_load_from_cache(
        MODEL_ID,
        "weights.safetensors",
        revision=MODEL_REVISION,
    )
    if not isinstance(cached_weights, str) or not Path(cached_weights).is_file():
        pytest.skip("the pinned model must already be cached; this test does not download it")

    with tempfile.TemporaryDirectory(
        prefix="mlx-whisper-integration-",
        dir=os.environ.get("TMPDIR"),
    ) as temporary:
        directory = Path(temporary)
        subprocess.run(
            ["say", "-o", str(directory / "sample.aiff"), "A synthetic recovery check."],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(directory / "sample.aiff"),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(directory / "sample.wav"),
            ],
            check=True,
            capture_output=True,
        )

        client = TestClient(create_app())
        with client:
            malformed = client.post(
                "/v1/audio/transcriptions",
                data={"model": MODEL_ALIAS},
                files={"file": ("malformed.wav", b"not a valid WAV", "audio/wav")},
            )
            health_after_failure = client.get("/health")
            recovered = client.post(
                "/v1/audio/transcriptions",
                data={"model": MODEL_ALIAS},
                files={
                    "file": (
                        "sample.wav",
                        (directory / "sample.wav").read_bytes(),
                        "audio/wav",
                    )
                },
            )
            health_after_recovery = client.get("/health")

        assert malformed.status_code == 503
        assert health_after_failure.json() == {"status": "starting"}
        assert recovered.status_code == 200
        assert recovered.json().get("text")
        assert health_after_recovery.json() == {"status": "ready"}
