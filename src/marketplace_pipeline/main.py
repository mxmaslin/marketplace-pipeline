"""CLI entrypoint shim."""

from marketplace_pipeline.interfaces.cli.main import main

__all__ = ["main"]

if __name__ == "__main__":
    import sys

    sys.exit(main())
