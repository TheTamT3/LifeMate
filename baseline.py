"""Compatibility entry point for the offline LifeMate baseline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lifemate.cli import main


if __name__ == "__main__":
    main()
