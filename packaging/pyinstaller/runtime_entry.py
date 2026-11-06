"""Entry point for the frozen S-Lang executable."""

# These imports are intentionally explicit. They force PyInstaller to include
# the compiler graph instead of relying on dynamic import discovery.
import slang  # noqa: F401
import slang.core  # noqa: F401
import slang.cli


if __name__ == "__main__":
    slang.cli.main()
