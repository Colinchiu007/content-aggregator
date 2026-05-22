"""
Content Aggregator Web UI startup script

Usage:
    python scripts/web.py              # port 8080
    python scripts/web.py --port 9000  # custom port
    python scripts/web.py --host 0.0.0.0  # allow external access
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser(description="Content Aggregator Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Listen address")
    parser.add_argument("--port", type=int, default=8080, help="Port")
    parser.add_argument("--reload", action="store_true", help="Hot reload (dev)")
    parser.add_argument("--config", type=str, help="Config file path")
    args = parser.parse_args()

    import uvicorn
    from web.server import app

    print()
    print("  Content Aggregator Web UI")
    print("  =========================")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  Config: {args.config or 'config/config.yaml'}")
    print("  Press Ctrl+C to stop")
    print()

    uvicorn.run(
        "web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).parent.parent / "web")],
        app_dir=str(Path(__file__).parent.parent),
    )


if __name__ == "__main__":
    main()