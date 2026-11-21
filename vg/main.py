"""
VG main entry point — Mini CID Investigator.

Default behavior:
  python -m vg.main
  python -m vg.main --web --port 8080
"""

import os
import sys

if __package__ in (None, ""):
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT in sys.path:
        sys.path.remove(PROJECT_ROOT)
    sys.path.insert(0, PROJECT_ROOT)


def _consume_option(argv: list[str], option: str, default: str) -> str:
    """Pop an option and its value from argv if present."""
    if option not in argv:
        return default
    index = argv.index(option)
    try:
        value = argv[index + 1]
    except IndexError as exc:
        raise SystemExit(f"{option} requires a value.")
    del argv[index:index + 2]
    return value


def run_web(argv: list[str]) -> None:
    """Run the browser-native web server."""
    host = _consume_option(argv, "--host", os.getenv("VG_HOST", "0.0.0.0"))
    port = int(_consume_option(argv, "--port", os.getenv("PORT", os.getenv("VG_PORT", "8080"))))
    from vg.api.server import run_server
    run_server(host=host, port=port)


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--web" in argv:
        argv = [arg for arg in argv if arg != "--web"]
    run_web(argv)
