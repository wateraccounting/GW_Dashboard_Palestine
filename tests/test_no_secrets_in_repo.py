"""Guard rail: fail if a real credential is about to be committed."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "node_modules"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----(\\n|\s)+[A-Za-z0-9+/=]{40,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "private_key_id": re.compile(r'"?private_key_id"?\s*[:=]\s*"[0-9a-f]{40}"'),
}


def candidate_files():
    try:  # prefer the exact list of files git would commit
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split("\n")
        files = [ROOT / f for f in out if f]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*") if p.is_file()]
    for p in files:
        if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
            yield p


def test_no_credentials_in_tracked_files():
    hits = []
    for p in candidate_files():
        if p.name == "secrets.toml":
            continue  # ignored by .gitignore; checked separately below
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in PATTERNS.items():
            for m in rx.finditer(text):
                if re.search(r"0{40}", m.group(0)):
                    continue  # the all-zero placeholder in secrets.toml.example
                hits.append(f"{p.relative_to(ROOT)}: {label}")
    assert not hits, "Possible credentials found – remove them before committing:\n" + "\n".join(hits)


def test_gitignore_protects_secrets():
    ignore = (ROOT / ".gitignore").read_text()
    for needed in (".streamlit/secrets.toml", "*.json", ".env"):
        assert needed in ignore


def test_secrets_file_is_not_tracked_by_git():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return  # not a git checkout (e.g. downloaded zip)
    assert "secrets.toml\n" not in out.replace("secrets.toml.example", "")
