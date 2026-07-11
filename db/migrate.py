"""CLI shim — prefer `python -m chime migrate` or `python -m chime.migrate`."""

from chime.migrate import main

if __name__ == "__main__":
    raise SystemExit(main())
