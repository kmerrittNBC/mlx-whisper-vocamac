from __future__ import annotations

import sys

from mlx_whisper_vocamac import cli


def test_server_defaults_to_loopback_port_8765(monkeypatch) -> None:
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda app, **kwargs: observed.update(app=app, **kwargs),
    )
    monkeypatch.setattr(sys, "argv", ["mlx-whisper-vocamac"])

    cli.main()

    assert observed == {
        "app": "mlx_whisper_vocamac.app:app",
        "host": "127.0.0.1",
        "port": 8765,
        "log_level": "info",
        "access_log": False,
    }
