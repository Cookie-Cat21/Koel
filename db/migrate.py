"""CLI shim — prefer `python -m koel migrate` or `python -m koel.migrate`."""

from koel.migrate import main

if __name__ == "__main__":
    raise SystemExit(main())
