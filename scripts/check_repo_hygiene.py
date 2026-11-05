"""Small CI bootstrap: reject obvious unsafe or malformed tracked repository files.

This is NOT a secret scanner, OCaml build check, trading safety proof,
or substitute for branch protection and human review.
"""

from pathlib import Path
import re
import subprocess
import sys

TEXT_SUFFIXES = {
    ".md", ".py", ".yml", ".yaml", ".toml", ".ml", ".mli", ".opam",
    ".sh", ".json", ".sql", ".txt", ".mdx",
}
BLOCKED_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pem", ".p12", ".pfx", ".key"}
PRIVATE_KEY_MARKER = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
ACTION = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[a-fA-F0-9]{40}$")


def inspect_file(relative_path: str, content: bytes) -> list[str]:
    """Return stable, readable errors for a tracked path and its bytes."""
    errors: list[str] = []
    path = Path(relative_path)
    name = path.name

    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        errors.append("private environment file is tracked")
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        errors.append("blocked key/database artifact extension")
    if PRIVATE_KEY_MARKER.search(content):
        errors.append("private key material is tracked")

    if path.suffix.lower() in TEXT_SUFFIXES or name in {".gitignore", ".editorconfig"}:
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append("source/configuration text must be valid UTF-8")
            return errors

        if b"\r" in content:
            errors.append("source/configuration text contains CR bytes")
        if content and not content.endswith(b"\n"):
            errors.append("source/configuration text lacks final newline")
        for number, line in enumerate(decoded.splitlines(), 1):
            if line.rstrip(" \t") != line:
                errors.append(f"trailing whitespace at line {number}")

        if relative_path.startswith(".github/workflows/"):
            for matched in ACTION.finditer(decoded):
                used_action = matched.group(1)
                if not used_action.startswith("./") and not PINNED_ACTION.fullmatch(used_action):
                    errors.append(f"external GitHub Action must be pinned to SHA: {used_action}")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    errors: list[str] = []
    for raw in tracked.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = root / relative
        if path.is_symlink():
            errors.append(f"{relative}: symbolic links need explicit review")
            continue
        for reason in inspect_file(relative, path.read_bytes()):
            errors.append(f"{relative}: {reason}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Repository hygiene: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
