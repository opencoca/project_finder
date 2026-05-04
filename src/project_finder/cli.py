"""project_finder — locate dev projects and emit per-project markdown notes.

Walks a directory tree, identifies every directory that looks like a project
root (contains ``.git``, or a recognised language marker file), and writes one
markdown file per project to an output dir. Each note carries YAML frontmatter
plus a short readable body with path, last-commit timestamp (for git projects),
remote URL (when present), and detected languages.

The vault layout mirrors the source tree: a project at
``<scan-root>/foo/bar/myproj`` lands at ``<vault>/foo/bar/myproj.md``. This
makes sibling relationships visible directly in Obsidian's file tree, gives
every note a unique output path by construction (no filename collisions
possible), and lets the file tree itself act as the navigation index.

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
import json
import os
import subprocess
import sys
import tomllib
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
    # `configure` (autotools) and `CMakeLists.txt` (CMake) are strong C/C++
    # signals on their own. Plain `Makefile` is *not* listed here because it
    # triggers false-positive project roots in non-code dirs (e.g.
    # `~/bin/Makefile`). The smart-C path below picks up Makefile-driven C
    # projects when a `*.c` / `*.h` / `*.cpp` sibling is present.
    "c": ("configure", "CMakeLists.txt"),
    "r": ("DESCRIPTION",),
}

# File extensions that confirm a Makefile lives next to actual C/C++ source.
# Lowercase only — case-sensitive comparison is the convention on most Unix
# project trees and avoids surprising matches on macOS' case-insensitive HFS+.
C_SOURCE_EXTENSIONS: tuple[str, ...] = (
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
)

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


def find_projects(
    scan_path: Path,
    include_hidden: bool = False,
    extra_excludes: frozenset[str] = frozenset(),
) -> list[Path]:
    """Return project roots (sorted) under *scan_path*.

    A project root is any directory that contains either ``.git`` (file or dir)
    or one of the recognised language marker files. The walker stops descending
    once a project root is found, so subprojects are not double-counted, and
    prunes ``EXCLUDED_DIR_NAMES | extra_excludes`` from the descent to skip
    dependency / build / cache trees.

    By default, **hidden directories (names starting with** ``.``\ **) are
    skipped entirely** — this catches tool-managed caches in a home directory
    (``~/.bun``, ``~/.cache``, ``~/.npm``, ``~/.cargo``, ``~/.pyenv``, ...)
    that would otherwise produce thousands of false-positive projects from
    the marker files inside cached packages. Pass ``include_hidden=True`` to
    walk into hidden dirs (useful when scanning e.g. ``~/.dotfiles``).

    *extra_excludes* layers user-supplied dir names on top of the hardcoded
    baseline — used for CLI ``--exclude-from`` and the auto-loaded
    ``<scan_path>/.project_finder_exclude`` file. Same matching semantics:
    plain directory names, matched anywhere in the tree.
    """
    excluded = EXCLUDED_DIR_NAMES | extra_excludes

    projects: list[Path] = []
    for current, dirs, files in os.walk(scan_path):
        current_path = Path(current)

        # A marker can show up as either a dir (`.git/`) or a file (`.git` for
        # submodules, every language marker file) — check both lists with the
        # single PROJECT_MARKERS set. The smart-C path additionally claims
        # Makefile-driven C projects without putting bare `Makefile` in the
        # marker set (which would re-introduce the `~/bin/Makefile` false
        # positive).
        is_project = (
            any(name in dirs or name in files for name in PROJECT_MARKERS)
            or _is_smart_c_project(files)
        )

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
            if d not in excluded
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


def _load_excludes(path: Path) -> frozenset[str]:
    """Return dir names listed in *path*, one per line. Blanks and ``#`` comments ignored.

    Missing or unreadable files yield an empty frozenset rather than raising —
    auto-loading from a conventional path (``<scan_path>/.project_finder_exclude``)
    is best-effort, and forcing the user to pre-create the file would be an
    unnecessary friction. The CLI ``--exclude-from`` path goes through the same
    helper but is treated as load-or-warn at the caller's discretion.
    """
    try:
        text = path.read_text()
    except OSError:
        return frozenset()

    names: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.add(line)
    return frozenset(names)


def _project_timestamp_str(project: Path) -> str:
    """Return the human-readable last-activity string for *project*.

    For git projects: the ISO-8601 UTC timestamp of HEAD's commit, or
    ``(no commits)`` for a fresh repo with nothing committed yet.

    For non-git projects: the ISO-8601 UTC of the project root directory's
    filesystem mtime — a coarse approximation of "when did this last move,"
    fine for change-detection at directory granularity but imperfect for
    deep edits in nested files. Returns ``(non-git project, no mtime)`` if
    even ``stat`` fails.
    """
    if (project / ".git").exists():
        ts = last_commit_timestamp(project)
        if ts is not None:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        return "(no commits)"
    try:
        ts = int(project.stat().st_mtime)
    except OSError:
        return "(non-git project, no mtime)"
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _existing_note_path(note_path: Path) -> str | None:
    """Read the ``path:`` value from a vault note's frontmatter, or ``None``.

    Same single-line scan technique as ``_existing_note_timestamp``: walks the
    file looking for a line that starts with ``path:`` and returns its value.
    Used by orphan detection — a note whose recorded source path no longer
    exists on disk is a candidate for pruning.
    """
    try:
        for line in note_path.read_text().splitlines():
            if line.startswith("path:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _detect_orphans(vault_root: Path) -> list[Path]:
    """Return vault notes whose recorded ``path:`` no longer exists on disk.

    A note without a ``path:`` field (i.e. not one of ours — user-created
    notes, README files, etc.) is left alone: orphan detection is opt-in by
    being a project_finder note in the first place.
    """
    orphans: list[Path] = []
    for md_file in vault_root.rglob("*.md"):
        source_path = _existing_note_path(md_file)
        if source_path is None:
            continue
        if not Path(source_path).exists():
            orphans.append(md_file)
    return orphans


def _prune_empty_ancestors(start: Path, stop: Path) -> None:
    """Remove *start*'s parent and any further empty ancestors, up to *stop*.

    Stops at *stop* (the vault root) to avoid deleting the vault itself.
    """
    current = start
    while current != stop and current.is_dir() and not any(current.iterdir()):
        current.rmdir()
        current = current.parent


def _existing_note_timestamp(note_path: Path) -> str | None:
    """Read ``last_commit:`` from a vault note's frontmatter, or return ``None``.

    Used by the incremental-scan path to decide whether a project's note is
    still fresh. We deliberately don't parse YAML — a single-line scan is
    sufficient because ``last_commit:`` is always emitted on its own line by
    ``emit_markdown``. Missing file or unreadable file → ``None`` (treat as
    a new project; the caller will emit).
    """
    try:
        for line in note_path.read_text().splitlines():
            if line.startswith("last_commit:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _python_metadata(repo: Path) -> dict | None:
    """Parse ``pyproject.toml`` ``[project]`` (PEP 621). Return ``None`` on miss.

    Returns ``{"name", "version", "dependencies"}`` (any field may be missing
    from the source data — callers tolerate ``None``). ``setup.py`` and bare
    ``requirements.txt`` projects are intentionally skipped: the former is
    Python *code* (would need exec), the latter has no name/version. PEP 621
    pyproject.toml covers the modern packaging path; that's enough for v1.
    """
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        data = tomllib.loads(pyproject.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return None
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    deps = project.get("dependencies", [])
    return {
        "name": project.get("name"),
        "version": project.get("version"),
        "description": project.get("description"),
        "dependencies": list(deps) if isinstance(deps, list) else [],
    }


def _node_metadata(repo: Path) -> dict | None:
    """Parse ``package.json``. Return ``None`` on miss.

    ``dependencies`` is the package's runtime deps (the keys of the
    ``dependencies`` object in ``package.json``). ``devDependencies`` are
    deliberately excluded — they're build-time noise for a vault overview.
    """
    package_json = repo / "package.json"
    if not package_json.exists():
        return None
    try:
        data = json.loads(package_json.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    deps = data.get("dependencies", {})
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "dependencies": list(deps.keys()) if isinstance(deps, dict) else [],
    }


def extract_metadata(repo: Path) -> dict:
    """Try each manifest parser and return the first non-empty result.

    Polyglot projects (e.g. Python + Node) currently surface only one source —
    Python is checked first, falling through to Node. The unified return shape
    is ``{"name": str|None, "version": str|None, "dependencies": list[str]}``;
    missing/unparsable manifests yield ``{}``.
    """
    for parser in (_python_metadata, _node_metadata):
        result = parser(repo)
        if result is not None:
            return result
    return {}


def _is_smart_c_project(files: list[str]) -> bool:
    """True if *files* contains a ``Makefile`` alongside any C/C++ source file.

    "Smart" because a bare ``Makefile`` is not enough on its own — it could
    be orchestration / docs / personal automation. Pairing it with at least
    one ``.c`` / ``.h`` / ``.cpp`` / ``.hpp`` sibling is what distinguishes a
    real Makefile-driven C project from a Makefile-using utility directory.
    """
    return "Makefile" in files and any(
        f.endswith(C_SOURCE_EXTENSIONS) for f in files
    )


def detect_languages(repo: Path) -> list[str]:
    """Return language slugs whose markers exist at *repo*'s root.

    A polyglot project (e.g. one with both ``pyproject.toml`` and ``package.json``)
    yields multiple slugs. Order follows ``LANGUAGE_MARKERS``' iteration, with
    the smart-C path appended last when it kicks in.
    """
    try:
        entries = os.listdir(repo)
    except OSError:
        return []

    languages = [
        lang
        for lang, markers in LANGUAGE_MARKERS.items()
        if any(m in entries for m in markers)
    ]
    # Smart-C path: claim `lang/c` for Makefile-plus-C-source dirs that didn't
    # match the strong `configure` / `CMakeLists.txt` markers above.
    if "c" not in languages and _is_smart_c_project(entries):
        languages.append("c")
    return languages


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


def _vault_output_path(project: Path, scan_root: Path, vault_root: Path) -> Path:
    """Return the markdown output path that mirrors *project* under *vault_root*.

    A project at ``<scan_root>/foo/bar/myproj`` lands at
    ``<vault_root>/foo/bar/myproj.md``. The two edge cases:

    * If *project* equals *scan_root* (the user pointed the scanner at a
      single project root), the relative path is ``.`` — fall back to
      ``<vault_root>/<project.name>.md``.
    * If *project* lives outside *scan_root* (shouldn't happen via
      ``os.walk(scan_root)`` but be defensive), do the same fallback so we
      never raise from a path-arithmetic edge.

    The ``f"{rel.name}.md"`` form is used instead of ``with_suffix`` so a
    project directory whose name contains dots (``app.robotinacan.com``)
    doesn't get its trailing component stripped.
    """
    try:
        rel = project.relative_to(scan_root)
    except ValueError:
        return vault_root / f"{project.name}.md"

    if rel == Path("."):
        return vault_root / f"{project.name}.md"

    return vault_root / rel.parent / f"{rel.name}.md"


def emit_markdown(
    project: Path,
    output_path: Path,
    timestamp_str: str,
) -> Path:
    """Write one markdown file describing *project* to *output_path*.

    Returns the path of the file written. The caller is responsible for
    making sure ``output_path.parent`` already exists (``mkdir(parents=True,
    exist_ok=True)`` from main); ``emit_markdown`` itself just opens and
    writes the file.

    *timestamp_str* is the human-readable last-activity string (precomputed
    by ``_project_timestamp_str`` in main, then reused here for the
    frontmatter and the body bullet — single source of truth, no double
    subprocess for git or double stat for filesystem).

    Output schema::

        ---
        name: <project basename>
        path: <absolute project path>
        package_name: <from manifest>      (only when manifest parsed)
        package_version: <from manifest>   (only when manifest parsed)
        last_commit: <ISO 8601 UTC | "(no commits)" | "(non-git project)">
        tags: [project, (git,) parent/<dir>, lang/<name>, ...]
        ---

        # <project basename>

        <description paragraph (optional)>

        - **Path**: [`<project path>`](vscode://file/<abs path>)
        - **Last commit**: <timestamp>             (omitted for non-git projects)
        - **Remote**: <host-url>                    (omitted if no origin)
        - **Languages**: <name>, <name>             (omitted if no markers)
        - **Dependencies (N)**: <dep1>, <dep2>, ... (omitted if none / unparsed)
    """
    # `exists()` covers both forms — .git as a directory (normal repo) and as
    # a file (submodule / secondary worktree pointing at git data elsewhere).
    is_git = (project / ".git").exists()

    # why double slash in the URI: vscode://file/<absolute-path> requires the
    # absolute path *with its leading /* to round-trip correctly. The first
    # slash belongs to the URI scheme separator, the second is the path's own.
    vscode_link = f"vscode://file/{project}"
    # host_repo_url returns None for non-git projects too (subprocess fails),
    # so no separate is_git guard is needed here.
    host_url = host_repo_url(project)
    languages = detect_languages(project)
    metadata = extract_metadata(project)
    package_name = metadata.get("name")
    package_version = metadata.get("version")
    description = metadata.get("description")
    dependencies = metadata.get("dependencies", [])

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

    # Frontmatter assembled in order; package_* slot in only when the manifest
    # gave us something. Conditional emission keeps the YAML clean for the
    # ~75% of projects that have no parseable manifest (yet).
    fm_lines = [f"name: {project.name}", f"path: {project}"]
    if package_name:
        fm_lines.append(f"package_name: {package_name}")
    if package_version:
        fm_lines.append(f"package_version: {package_version}")
    fm_lines.append(f"last_commit: {timestamp_str}")
    fm_lines.append(f"tags: [{', '.join(tags)}]")

    bullets = [f"- **Path**: [`{project}`]({vscode_link})"]
    if is_git:
        bullets.append(f"- **Last commit**: {timestamp_str}")
    if host_url:
        bullets.append(f"- **Remote**: <{host_url}>")
    if languages:
        bullets.append(f"- **Languages**: {', '.join(languages)}")
    if dependencies:
        # Truncate the visible list at 5 to keep notes scannable; the count
        # is in the bullet header so the full size is never hidden.
        shown = dependencies[:5]
        more = len(dependencies) - len(shown)
        deps_str = ", ".join(shown) + (f", ... ({more} more)" if more else "")
        bullets.append(f"- **Dependencies ({len(dependencies)})**: {deps_str}")

    fm = "\n".join(fm_lines)
    body = "\n".join(bullets)
    # Description sits between H1 and bullets when present — a real paragraph
    # of human-readable context above the metadata grid. Blank line separator
    # before the bullets so Markdown renders the description as a paragraph.
    description_block = f"\n{description}\n" if description else ""

    output_path.write_text(
        f"""---
{fm}
---

# {project.name}
{description_block}
{body}
"""
    )
    return output_path


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
    parser.add_argument(
        "--exclude-from",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Read additional excluded dir names from FILE (one per line, "
            "'#' comments and blank lines ignored). Layered on top of the "
            "built-in baseline and any auto-loaded "
            "<scan-path>/.project_finder_exclude file."
        ),
    )
    parser.add_argument(
        "--prune-orphans",
        action="store_true",
        help=(
            "Delete vault notes whose recorded source path no longer exists "
            "(and remove any directories left empty as a result). Without "
            "this flag, orphans are listed to stderr but not touched — "
            "deletion is destructive and the vault may not be under git."
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

    # Layer extra excludes from --exclude-from (explicit) and from
    # <scan_path>/.project_finder_exclude (auto-detected, best-effort).
    extra_excludes: frozenset[str] = frozenset()
    if args.exclude_from is not None:
        extra_excludes |= _load_excludes(args.exclude_from.expanduser())
    extra_excludes |= _load_excludes(scan_path / ".project_finder_exclude")

    projects = find_projects(
        scan_path,
        include_hidden=args.include_hidden,
        extra_excludes=extra_excludes,
    )
    hidden_note = "" if args.include_hidden else " (hidden dirs skipped — pass --include-hidden to walk them)"
    excludes_note = f" (+{len(extra_excludes)} extra exclude(s))" if extra_excludes else ""
    print(f"Found {len(projects)} projects under {scan_path}{hidden_note}{excludes_note}.")

    # Output path mirrors the source tree: project at <scan_root>/foo/bar/myproj
    # writes to <out_dir>/foo/bar/myproj.md. Uniqueness is by construction, no
    # disambiguation needed — and the file tree is the navigation index.
    written = 0
    skipped = 0
    failed = 0
    for project in projects:
        # Per-project resilience: one corrupt project (broken .git, unreadable
        # manifest, etc.) shouldn't block all subsequent emits. We log the
        # failure to stderr, increment the counter, and continue. The non-zero
        # exit code at the bottom keeps the "fail loud" signal for shell users.
        try:
            output_path = _vault_output_path(project, scan_path, out_dir)
            new_ts_str = _project_timestamp_str(project)
            existing_ts_str = _existing_note_timestamp(output_path)

            if existing_ts_str is not None and existing_ts_str == new_ts_str:
                skipped += 1
                print(f"  - {project} -> {output_path.relative_to(out_dir)} (unchanged, skipped)")
                continue

            # mkdir before write so emit_markdown only has to worry about content.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            out_file = emit_markdown(project, output_path, new_ts_str)
            written += 1
            print(f"  - {project} -> {out_file.relative_to(out_dir)}")
        except Exception as exc:
            failed += 1
            print(f"  ! {project}: {exc}", file=sys.stderr)

    skipped_note = f" ({skipped} unchanged, skipped)" if skipped else ""
    print(f"\nWrote {written} markdown files under {out_dir}{skipped_note}.")

    # Orphan detection: notes whose recorded source path no longer exists.
    # Always reported; only deleted when --prune-orphans is explicitly set.
    orphans = _detect_orphans(out_dir)
    if orphans:
        action = "Deleting" if args.prune_orphans else "Found"
        print(
            f"\n{action} {len(orphans)} orphan note(s) "
            f"(source path missing):",
            file=sys.stderr,
        )
        for orphan in orphans:
            print(f"  - {orphan.relative_to(out_dir)}", file=sys.stderr)
        if args.prune_orphans:
            for orphan in orphans:
                parent = orphan.parent
                orphan.unlink()
                _prune_empty_ancestors(parent, out_dir)
        else:
            print("Pass --prune-orphans to delete them.", file=sys.stderr)

    # Non-zero exit when any project failed to emit. Lets shells / CI / wrappers
    # detect partial-failure runs without parsing stderr — clean run exits 0.
    if failed:
        print(
            f"\n{failed} project(s) failed to emit — see stderr above.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
