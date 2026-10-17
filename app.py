"""Xairex entry point.

Usage:
  python app.py                 run the assistant in the terminal
  python app.py --gui           run the desktop GUI (Tkinter, Phase G)
  python app.py --check         run offline readiness checks and exit
                                (used by scripts/check_offline.ps1; exit code 1 on failure)
  python app.py --config PATH   use a different settings.json
"""

from __future__ import annotations

import argparse
import sys

from xairex import __version__
from xairex.config import ConfigError, load_settings
from xairex.health import run_health_checks
from xairex.logging_config import setup_logging
from xairex.runtime import Runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xairex", description="Xairex - fully offline personal voice assistant")
    parser.add_argument("--config", default=None, help="path to settings.json (default: config/settings.json)")
    parser.add_argument("--check", action="store_true", help="run offline readiness checks and exit")
    parser.add_argument("--gui", action="store_true", help="start the desktop GUI (Tkinter) instead of the terminal")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"[config] {exc}", file=sys.stderr)
        return 2

    logger = setup_logging(settings)
    logger.debug("Xairex %s starting (config: %s)", __version__, settings.config_path)

    if args.check:
        report = run_health_checks(settings)
        print(report.render())
        return 0 if report.ok else 1

    if args.gui:
        try:
            from xairex.gui.app import run_gui
        except ImportError as exc:  # tkinter missing from this Python install
            print(
                f"[gui] the desktop GUI needs tkinter ({exc}); run without --gui for the terminal.",
                file=sys.stderr,
            )
            return 2
        try:
            return run_gui(settings)
        except KeyboardInterrupt:
            return 0

    runtime = Runtime(settings)
    try:
        return runtime.run()
    except KeyboardInterrupt:
        runtime.shutdown()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
