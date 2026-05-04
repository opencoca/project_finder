# Changelog

All notable changes to `project_finder` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For finer-grained per-card history (rationale, edge cases, follow-ups), see
[TODO.md](TODO.md)'s `## Done` section.

## [0.1.0] - 2026-05-03 (unreleased)

First release-ready cut: end-to-end pipeline from a directory tree to a
path-mirrored Obsidian vault, with per-project resilience and incremental
re-scans.

### Added

- **Smallest Prototype** — Walk a tree, find dirs containing `.git`, emit one
  markdown file per repo with path + last-commit timestamp. Python stdlib only.
- **Vault Note Enrichment v1** — `parent/<dir>` tag, one `lang/<name>` tag per
  detected language, and a `Remote` bullet linking to the host repo (SSH→HTTPS
  normalized, `.git` stripped).
- **Disambiguate Filenames + VSCode Links** — `vscode://file/<abs-path>` link
  in each note's `Path` bullet so a single click in Obsidian opens the project
  in VSCode.
- **Project Discovery Walker** — `os.walk`-based discovery that detects any
  project root by marker (git or language file), stops descending once a root
  is identified, prunes common dependency / build / cache directories.
- **Skip Hidden Dirs by Default** — Walker skips dot-prefixed directories
  (`~/.bun`, `~/.cache`, etc.) by default; `--include-hidden` opts back in.
  Also prunes macOS `Library/Caches`, `Library/Containers`,
  `Library/Application Support`.
- **Smart C Detection** — Claims a directory as a C project when a `Makefile`
  is paired with at least one `.c` / `.h` / `.cpp` / `.hpp` sibling, without
  re-introducing the bare-Makefile false positive.
- **External Excludes File** — `--exclude-from FILE` flag and auto-loaded
  `<scan-path>/.project_finder_exclude` layer additional dir names on top of
  the hardcoded baseline.
- **Project Metadata Extraction v1 (Python + Node)** — Parses `pyproject.toml`
  (PEP 621) and `package.json`; emits `package_name` / `package_version` in
  frontmatter and a truncated `Dependencies (N)` bullet in the body.
- **Git-Aware Incremental Scan** — Re-runs skip projects whose last-commit
  timestamp matches the existing note. Falls back to filesystem mtime for
  non-git projects.
- **Obsidian Markdown Emitter v1** — Manifest-derived description paragraph
  rendered between the H1 and the metadata bullets.
- **Mirror Path Ontology in Vault** — A project at `<scan-root>/foo/bar/myproj`
  writes to `<vault>/foo/bar/myproj.md`. Filename collisions are impossible by
  construction; sibling relationships are visible in Obsidian's file tree.
- **Detect & Prune Orphan Notes** — Vault notes whose recorded source path no
  longer exists are reported by default; `--prune-orphans` deletes them and
  cleans up newly-empty ancestor directories.
- **Per-project failure resilience** — One corrupt project no longer crashes
  the whole scan. Failures are logged to stderr, the loop continues, and the
  process exits with code `1` if any project failed.

### Tools

- **TodoScope Alignment** — Bootstrap the repository for kanban scanning with
  `.todoscope-exclude.csv` and a `TODO.md` following the documented column
  conventions.

[0.1.0]: https://github.com/sommaalexander/project_finder/releases/tag/v0.1.0
