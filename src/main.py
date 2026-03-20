"""
Main entry point for Swarm.
"""

import sys

from .cli.app import app
from .cli.setup import run_setup

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        run_setup()
    else:
        app()