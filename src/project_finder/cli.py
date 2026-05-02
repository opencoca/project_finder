"""project_finder — locate dev projects and emit per-project markdown notes.

Walks a directory tree, identifies every directory that looks like a project
root (contains ``.git``, or a recognised language marker file), and writes one
markdown file per project to an output dir. Each note carries YAML frontmatter
plus a short readable body with path, last-commit timestamp (for git projects),
remote URL (when present), and detected languages.

Output filenames use ``<parent-dir>_<project-name>.md`` so that two projects
sharing a basename (e.g. two ``notes`` repos in different parents) get distinct
files. Projects at filesystem roots — where there is no meaningful parent dir
name — fall back to ``<project-name>.md``.

The path bullet in each note is rendered as a ``vscode://file/<abs-path>`` link,
so a single click in Obsidian opens the project in VSCode. When the project is
a git repo with an ``origin`` remote, a ``Remote`` bullet links to the host
(GitHub/GitLab/etc).

Tags emitted on each note:
    * ``project`` — universal
    * ``git`` — only when the project is a git repo
    * ``parent/<dir>`` — the project's containing directory, useful for
      grouping and colouring in Obsidian's graph view
    * ``lang/<name>`` — one per language whose marker file exists at the
      project root (python, node, ruby, swift, perl, c, r)

Discovery rules:
    * The walker stops descending once a project root is found, so subprojects
      under an outer project are not double-counted.
    * Common dependency / build / cache directories (``node_modules``,
      ``__pycache__``, ``.venv``, ``target``, ``build``, ``dist``, ``vendor``,
      tool caches) are pruned from the descent.
    * **Hidden directories (names starting with ``.``) are skipped by default.**
      Tool-managed dotdirs in a home directory (``~/.bun``, ``~/.cache``,
      ``~/.npm``, ``~/.cargo``, ``~/.pyenv``, ...) contain thousands of
      installed packages with marker files that would each be mis-claimed as
      a "project." The ``--include-hidden`` flag overrides this for the rare
      case of dot-prefixed project repos like ``~/.dotfiles``.
    * On macOS, ``Library/Caches``, ``Library/Containers``, and
      ``Library/Application Support`` are pruned for the same reason.

Usage::

    project_finder <scan-path> [vault-output-path] [--include-hidden]
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_VAULT_DIRNAME = "vault"

# Marker files (in a project's root) that imply a particular language.
# Order is the order tags are emitted; each entry's tuple lists the marker
# filenames any one of which is sufficient to claim the language.
LANGUAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "requirements.txt"),
    "node": ("package.json",),
    "ruby": ("Gemfile",),
    "swift": ("Package.swift",),
    "perl": ("Makefile.PL", "cpanfile"),
    # why no plain "Makefile": Makefile is a weak signal — it shows up in dirs
    # that orchestrate builds, generate docs, or run personal automation
    # (e.g. `~/bin/Makefile`) and triggers false-positive project detection
    # that prevents descent into real subprojects. `configure` and CMake are
    # strong signals; bare C projects with only a Makefile are rare enough
    # that opting them in via a future config flag is the right move.
    "c": ("configure", "CMakeLists.txt"),
    "r": ("DESCRIPTION",),
}

# Every name (file or dir) that signals "this directory is a project root."
# Derived from LANGUAGE_MARKERS plus `.git`, so adding a language to the dict
# above automatically extends discovery and tagging in lockstep.
PROJECT_MARKERS: frozenset[str] = frozenset(
    {".git"} | {marker for markers in LANGUAGE_MARKERS.values() for marker in markers}
)

# Directories the walker should never descend into. Catches the noise that
# inflates project counts and slows scans on large trees. ``.git`` is *not*
# excluded here because we want to detect it as a project marker — but the
# walker stops descending into a project root once found, so .git internals
# are never visited anyway.
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    "node_modules",
    "__pycache__",
    "venv",
    "target",
    "build", "dist",
    "vendor",
    # macOS Library noise — Caches and Containers are pure clutter; Application
    # Support holds Electron app internals (lots of bundled package.json) that
    # we don't want claimed as user projects.
    "Caches", "Containers", "Application Support",
})
# Note: dotdirs (`.venv`, `.cache`, `.bun`, ...) are not listed here because
# the dotdir prune in `find_projects` handles all of them in one rule. Adding
# specific names here would just duplicate that intent.


def find_projects(scan_path: Path, include_hidden: bool = False) -> list[Path]:
    """Return project roots (sorted) under *scan_path*.

    A project root is any directory that contains either ``.git`` (file or dir)
    or one of the recognised language marker files. The walker stops descending
    once a project root is found, so subprojects are not double-counted, and
    prunes ``EXCLUDED_DIR_NAMES`` from the descent to skip dependency / build /
    cache trees.

    By default, **hidden directories (names starting with** ``.``\ **) are
    skipped entirely** — this catches tool-managed caches in a home directory
    (``~/.bun``, ``~/.cache``, ``~/.npm``, ``~/.cargo``, ``~/.pyenv``, ...)
    that would otherwise produce thousands of false-positive projects from
    the marker files inside cached packages. Pass ``include_hidden=True`` to
    walk into hidden dirs (useful when scanning e.g. ``~/.dotfiles``).
    """
    projects: list[Path] = []
    for current, dirs, files in os.walk(scan_path):
        current_path = Path(current)

        # A marker can show up as either a dir (`.git/`) or a file (`.git` for
        # submodules, every language marker file) — check both lists with the
        # single PROJECT_MARKERS set.
        is_project = any(name in dirs or name in files for name in PROJECT_MARKERS)

        if is_project:
            projects.append(current_path)
            # why mutate dirs in place: this is the documented os.walk(topdown=True)
            # idiom for controlling descent. Emptying dirs prevents walking into
            # the project's own internals — that's how "stop at project root,
            # don't double-count subprojects" is enforced.
            dirs[:] = []
            continue

        # Not a project root. Prune excluded names, and (by default) hidden
        # dotdirs. The dotdir rule is poka-yoke: it makes "scan ~" sane by
        # default, and the override is one explicit flag away.
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIR_NAMES
            and (include_hidden or not d.startswith("."))
        ]

    return sorted(projects)


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


def emit_markdown(project: Path, ts: int | None, out_dir: Path) -> Path:
    """Write one markdown file describing *project* into *out_dir*.

    Returns the path of the file written.

    *ts* is the project's last-commit Unix timestamp for git projects, or
    ``None`` for git projects with no commits and for non-git projects. The
    function distinguishes the latter two by checking for ``.git`` directly.

    Output schema::

        ---
        name: <project basename>
        path: <absolute project path>
        last_commit: <ISO 8601 UTC | "(no commits)" | "(non-git project)">
        tags: [project, (git,) parent/<dir>, lang/<name>, ...]
        ---

        # <project basename>

        - **Path**: [`<project path>`](vscode://file/<abs path>)
        - **Last commit**: <timestamp>      (omitted for non-git projects)
        - **Remote**: <host-url>            (omitted if no origin)
        - **Languages**: <name>, <name>     (omitted if no markers detected)
    """
    # `exists()` covers both forms — .git as a directory (normal repo) and as
    # a file (submodule / secondary worktree pointing at git data elsewhere).
    is_git = (project / ".git").exists()

    if ts is not None:
        timestamp_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    elif is_git:
        timestamp_str = "(no commits)"
    else:
        timestamp_str = "(non-git project)"

    # why double slash in the URI: vscode://file/<absolute-path> requires the
    # absolute path *with its leading /* to round-trip correctly. The first
    # slash belongs to the URI scheme separator, the second is the path's own.
    vscode_link = f"vscode://file/{project}"
    # host_repo_url returns None for non-git projects too (subprocess fails),
    # so no separate is_git guard is needed here.
    host_url = host_repo_url(project)
    languages = detect_languages(project)

    # Build tag list deterministically: universal tag first, conditional `git`,
    # then parent, then language tags in LANGUAGE_MARKERS order. Nested tags
    # (with `/`) let Obsidian group and colour cards by parent or language in
    # the graph view.
    tags = ["project"]
    if is_git:
        tags.append("git")
    if project.parent.name:
        tags.append(f"parent/{project.parent.name}")
    tags.extend(f"lang/{lang}" for lang in languages)

    bullets = [f"- **Path**: [`{project}`]({vscode_link})"]
    if is_git:
        bullets.append(f"- **Last commit**: {timestamp_str}")
    if host_url:
        bullets.append(f"- **Remote**: <{host_url}>")
    if languages:
        bullets.append(f"- **Languages**: {', '.join(languages)}")

    body = "\n".join(bullets)
    tags_line = ", ".join(tags)

    out_file = out_dir / _vault_filename(project)
    out_file.write_text(
        f"""---
name: {project.name}
path: {project}
last_commit: {timestamp_str}
tags: [{tags_line}]
---

# {project.name}

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
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help=(
            "Walk into hidden directories (names starting with '.'). "
            "Off by default — keeps ~/.bun, ~/.cache, ~/.npm and other "
            "tool-managed dotdirs out of the scan. Turn on for e.g. ~/.dotfiles."
        ),
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

    projects = find_projects(scan_path, include_hidden=args.include_hidden)
    hidden_note = "" if args.include_hidden else " (hidden dirs skipped — pass --include-hidden to walk them)"
    print(f"Found {len(projects)} projects under {scan_path}{hidden_note}.")

    # Track which filenames have been written and from where, so we can warn
    # the user about ``parent_name`` collisions instead of silently dropping
    # earlier projects when a later one overwrites the same filename. The
    # naming-scheme fix is a separate follow-up; this is the poka-yoke.
    seen: dict[str, list[Path]] = {}
    for project in projects:
        # last_commit_timestamp returns None for non-git projects too — git -C
        # on a non-repo errors and the broad except clause yields None — so the
        # downstream emit_markdown logic handles both cases uniformly.
        ts = last_commit_timestamp(project)
        out_file = emit_markdown(project, ts, out_dir)
        seen.setdefault(out_file.name, []).append(project)
        print(f"  - {project} -> {out_file.name}")

    collisions = {fn: paths for fn, paths in seen.items() if len(paths) > 1}
    print(f"\nWrote {len(projects) - sum(len(p) - 1 for p in collisions.values())} markdown files to {out_dir}.")
    if collisions:
        print(
            f"\nWARNING: {len(collisions)} filename collision(s) — later writes "
            f"overwrote earlier ones. Affected projects:",
            file=sys.stderr,
        )
        for fn, paths in collisions.items():
            print(f"  {fn}:", file=sys.stderr)
            for p in paths:
                print(f"    - {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
