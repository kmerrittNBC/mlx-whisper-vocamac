from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local MLX Whisper API for VocaMac.")
    parser.add_argument(
        "--port", type=int, default=8765, help="Loopback HTTP port (default: 8765)."
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(
        "mlx_whisper_vocamac.app:app",
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
