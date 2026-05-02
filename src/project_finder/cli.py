"""project_finder — locate git repositories and emit per-repo markdown notes.

Smallest-possible scope of the eventual vault generator: walk a directory tree,
find every directory that contains a ``.git`` directory (i.e. each git working
tree's root), and write one markdown file per repository to an output dir. The
markdown carries YAML frontmatter with the repo path and the timestamp of the
last commit, plus a short readable body.

Out of scope (deliberately) for this prototype:
    * Detecting non-git project markers (package.json, pyproject.toml, ...)
    * Hardlinking the source tree into the vault
    * Wiki-style cross-links between projects
    * Incremental / change-aware re-runs

Output filenames use ``<parent-dir>_<repo-name>.md`` so that two repos sharing
a basename (e.g. two ``notes`` repos in different parents) get distinct files.
Repos at filesystem roots — where there is no meaningful parent dir — fall back
to ``<repo-name>.md``.

The path bullet in each note is rendered as a ``vscode://file/<abs-path>`` link,
so a single click in Obsidian opens the repo in VSCode. When the repo has an
``origin`` remote, a ``Remote`` bullet links to the host (GitHub/GitLab/etc).

Tags emitted on each note:
    * ``project``, ``git`` — universal
    * ``parent/<dir>`` — the repo's containing directory, useful for grouping
      and colouring in Obsidian's graph view
    * ``lang/<name>`` — one per language whose marker file exists at the repo
      root (python, node, ruby, swift, perl, c, r)

Usage::

    project_finder <scan-path> [vault-output-path]
"""

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_VAULT_DIRNAME = "vault"

# Marker files (in a repo's root) that imply a particular language.
# Order is the order tags are emitted; each entry's tuple lists the marker
# filenames any one of which is sufficient to claim the language.
LANGUAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "requirements.txt"),
    "node": ("package.json",),
    "ruby": ("Gemfile",),
    "swift": ("Package.swift",),
    "perl": ("Makefile.PL", "cpanfile"),
    "c": ("Makefile", "configure", "CMakeLists.txt"),
    "r": ("DESCRIPTION",),
}


def find_git_repos(scan_path: Path) -> list[Path]:
    """Return repo roots (sorted) under *scan_path*.

    A "repo root" is a directory that directly contains a ``.git`` *directory*.
    """
    # why is_dir(): .git can also be a *file* (submodule pointer or secondary
    # worktree gitfile). Those point at a git dir elsewhere; treating them as
    # repo roots would yield confusing duplicate cards for the same history.
    return sorted(
        git_dir.parent
        for git_dir in scan_path.rglob(".git")
        if git_dir.is_dir()
    )


def last_commit_timestamp(repo: Path) -> int | None:
    """Return Unix epoch seconds of HEAD's commit, or ``None`` if unavailable.

    Returns ``None`` for repos with no commits yet, or any subprocess/parse
    failure (corrupt repos, missing git binary, etc.). Callers handle ``None``.
    """
    # why catch broadly: several failure modes (no commits, corrupt index, git
    # binary missing, permission denied) all collapse to "no timestamp" — and
    # we render the same "(no commits)" string for the lot rather than try to
    # distinguish them at this layer.
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def detect_languages(repo: Path) -> list[str]:
    """Return language slugs whose marker files exist at *repo*'s root.

    A polyglot project (e.g. one with both ``pyproject.toml`` and ``package.json``)
    yields multiple slugs. Order follows ``LANGUAGE_MARKERS``' iteration order
    for deterministic output across runs.
    """
    return [
        lang
        for lang, markers in LANGUAGE_MARKERS.items()
        if any((repo / m).exists() for m in markers)
    ]


def host_repo_url(repo: Path) -> str | None:
    """Return a browser-friendly URL for *repo*'s ``origin`` remote, or ``None``.

    Normalizes SSH-style URLs (``git@github.com:owner/repo.git``) to HTTPS form
    (``https://github.com/owner/repo``) and strips trailing ``.git``. Returns
    ``None`` when the repo has no ``origin`` remote, the remote URL is empty,
    or git fails for any reason.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    url = result.stdout.strip()
    if not url:
        return None

    # why replace only the *first* colon: SSH URLs use ``host:path`` (one colon
    # between host and path), but the path itself can contain colons in rare
    # cases. HTTPS form needs that first colon converted to a slash and nothing
    # else touched.
    if url.startswith("git@"):
        url = "https://" + url.removeprefix("git@").replace(":", "/", 1)

    return url.removesuffix(".git")


def _vault_filename(repo: Path) -> str:
    """Return the markdown filename for *repo* in the vault.

    Uses ``<parent-dir>_<repo-name>.md`` so two repos sharing a basename — the
    common collision case (e.g. ``~/work/notes`` and ``~/personal/notes``) —
    end up with distinct output files. Repos at a filesystem root (no parent
    dir name available) fall back to ``<repo-name>.md``.
    """
    # why guard the empty-parent case: Path('/repo').parent is Path('/'), and
    # Path('/').name is ''. Without this guard we'd produce '_repo.md' with a
    # leading underscore, which sorts oddly and looks like a hidden file.
    parent_name = repo.parent.name
    return f"{parent_name}_{repo.name}.md" if parent_name else f"{repo.name}.md"


def emit_markdown(repo: Path, ts: int | None, out_dir: Path) -> Path:
    """Write one markdown file describing *repo* into *out_dir*.

    Returns the path of the file written.

    Output schema::

        ---
        name: <repo basename>
        path: <absolute repo path>
        last_commit: <ISO 8601 UTC, or "(no commits)">
        tags: [project, git, parent/<dir>, lang/<name>, ...]
        ---

        # <repo basename>

        - **Path**: [`<repo path>`](vscode://file/<abs path>)
        - **Last commit**: <timestamp>
        - **Remote**: <host-url>            (omitted if no origin)
        - **Languages**: <name>, <name>     (omitted if no markers detected)

    The path bullet links to the VSCode URI for the repo so a single click in
    Obsidian opens the working tree in VSCode. The remote bullet, when present,
    links to the host repo (GitHub/GitLab/etc) via its browser URL.
    """
    timestamp_str = (
        datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        if ts is not None
        else "(no commits)"
    )
    # why double slash in the URI: vscode://file/<absolute-path> requires the
    # absolute path *with its leading /* to round-trip correctly. The first
    # slash belongs to the URI scheme separator, the second is the path's own.
    vscode_link = f"vscode://file/{repo}"
    host_url = host_repo_url(repo)
    languages = detect_languages(repo)

    # Build tag list deterministically: universal tags first, then parent, then
    # language tags in LANGUAGE_MARKERS order. Nested tags (with `/`) let
    # Obsidian group and colour cards by parent or language in the graph view.
    tags = ["project", "git"]
    if repo.parent.name:
        tags.append(f"parent/{repo.parent.name}")
    tags.extend(f"lang/{lang}" for lang in languages)

    bullets = [
        f"- **Path**: [`{repo}`]({vscode_link})",
        f"- **Last commit**: {timestamp_str}",
    ]
    if host_url:
        bullets.append(f"- **Remote**: <{host_url}>")
    if languages:
        bullets.append(f"- **Languages**: {', '.join(languages)}")

    body = "\n".join(bullets)
    tags_line = ", ".join(tags)

    out_file = out_dir / _vault_filename(repo)
    out_file.write_text(
        f"""---
name: {repo.name}
path: {repo}
last_commit: {timestamp_str}
tags: [{tags_line}]
---

# {repo.name}

{body}
"""
    )
    return out_file


def main() -> None:
    """Entry point for the ``project_finder`` console script."""
    parser = argparse.ArgumentParser(
        prog="project_finder",
        description=(
            "Walk a directory tree, locate git repositories, and emit one "
            "markdown note per repo with path and last-commit timestamp."
        ),
    )
    parser.add_argument(
        "scan_path",
        type=Path,
        help="Root directory to scan for git repositories.",
    )
    parser.add_argument(
        "vault_output_path",
        type=Path,
        nargs="?",
        default=None,
        help=f"Where to write markdown files. Default: ./{DEFAULT_VAULT_DIRNAME}",
    )
    args = parser.parse_args()

    # Resolve user paths once up front so all downstream code works in absolute
    # terms — argparse hands us literal strings/Paths that may be ~-prefixed
    # or relative to CWD at invocation, neither of which we want to re-resolve
    # later in the loop.
    scan_path = args.scan_path.expanduser().resolve()
    out_dir = (
        args.vault_output_path
        if args.vault_output_path is not None
        else Path.cwd() / DEFAULT_VAULT_DIRNAME
    ).expanduser().resolve()

    if not scan_path.is_dir():
        raise SystemExit(f"scan_path {scan_path} is not a directory")

    out_dir.mkdir(parents=True, exist_ok=True)

    repos = find_git_repos(scan_path)
    print(f"Found {len(repos)} git repos under {scan_path}.")

    for repo in repos:
        ts = last_commit_timestamp(repo)
        out_file = emit_markdown(repo, ts, out_dir)
        print(f"  - {repo} -> {out_file.name}")

    print(f"\nWrote {len(repos)} markdown files to {out_dir}.")


if __name__ == "__main__":
    main()
