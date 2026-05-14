import sys
import argparse
from engine.config import load_config
from engine import orchestrator, progress


def main():
    # Print Python version at startup
    print(f"[RepoRelic] Python version: {sys.version}")
    print(f"[RepoRelic] Python executable: {sys.executable}")
    
    parser = argparse.ArgumentParser(description="RepoRelic Python Analysis Engine")
    parser.add_argument("target", nargs="?", help="Path to the target codebase")
    parser.add_argument("--check-deps", action="store_true",
                        help="Check which dependencies are installed and exit")
    args = parser.parse_args()

    if args.check_deps:
        _check_deps()
        return

    if not args.target:
        parser.print_help()
        sys.exit(1)

    orchestrator.run(args.target)


def _check_deps():
    """Report missing / found packages as JSON so the extension can prompt the user."""
    import json
    packages = ["networkx", "radon", "pylint", "pyflakes",
                "google.genai", "jinja2", "dotenv"]
    missing, found = [], []
    for pkg in packages:
        try:
            __import__(pkg)
            found.append(pkg)
        except ImportError:
            missing.append(pkg)
    print(json.dumps({"missing": missing, "found": found}))


if __name__ == "__main__":
    main()
