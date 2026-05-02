# TODO — project_finder

> **Convention** — Sections below map to kanban columns. Inline source-code
> tags use the same vocabulary so items stay cross-referenced between this
> file and the codebase. `KANBAN.canvas` auto-generates from this file and
> inline tags — do not hand-edit it.
>
> | Column      | Markdown section  | Inline tag  |
> |-------------|-------------------|-------------|
> | Backlog     | `## Backlog`      |             |
> | TODO        | `## TODO`         | `# TODO:`   |
> | In Progress | `## In Progress`  | `# FIXME:`  |
> | Bugs        | `## Bugs`         | `# BUG:`    |
> | Done        | `- [x]` items / `## Done` | —   |
>
> `# DEPRECATED:` tags should be tracked as TODO items for removal at the
> stated version.

A heuristic harness that locates dev projects in a folder and generates
intelligent Obsidian documentation vaults. See [README.md](README.md) for the
product description.

## In Progress

_No active card. Pull the next one from `## TODO` when ready._

## TODO

### Prototype Follow-ups

- [ ] **Project Note Structure**: Add a per-note `## Structure` section listing the project's top-level files and immediate subdirs (skipping `.git`, `__pycache__`, etc.). Useful for at-a-glance "what does this project look like" without leaving Obsidian. Keep it shallow (top level only) — full tree is overwhelming.

- [ ] **Re-emit on Description Change (Incremental Scan v2)**: Current incremental scan compares only `last_commit:`. If a manifest's `description` changes without a commit moving, the existing note stays stale. Possible fix: extend the comparison to a hash of `(timestamp + description)` stored in frontmatter, or add a `--force-rebuild` flag.

- [ ] **Shared-Dependency Wikilinks**: Generate edges between projects that share a runtime dependency (e.g. all `react`-using projects link to each other or to a common phantom node). Higher graph density, but requires a global dependency map computed before any note is written.

- [ ] **Project Metadata v2 — Other Manifests**: Add metadata parsers for Ruby (`Gemfile.lock` — easier to parse than the Ruby-code `Gemfile`), Swift (parse the simple subset of `Package.swift` or fall back to `swift package describe --type json`), C (`CMakeLists.txt` `project()` directive), R (`DESCRIPTION` is colon-separated key/value, easy). Perl manifests are Perl code — defer indefinitely. Each parser plugs into `extract_metadata`'s orchestrator the same way `_python_metadata` / `_node_metadata` do.

### Phase 3 — Vault Generation

- [ ] **Hardlinked Source References**: Filesystem links from vault to source
  - [ ] Detect existing hardlink count before writing (preserve inode if present)
  - [ ] Create hardlinks (not symlinks) from vault into project source dirs
  - [ ] Handle cross-filesystem case gracefully (warn, fall back to symlink or skip)

### Quality & Release

- [ ] **Test Harness**: Cover the scanner and emitter
  - [ ] Fixture directory with one project of each supported language
  - [ ] Snapshot tests for emitted markdown
  - [ ] Test incremental re-run skips unchanged projects

- [ ] **CLI Polish**: First-run UX
  - [ ] `--help` with usage and flag list
  - [ ] Sensible default for `vault-output-path` if omitted
  - [ ] Progress output during scan
  - [ ] Exit codes for partial failures

- [ ] **Packaging & Install**: Make it runnable from `~/bin`
  - [ ] Shebang / entry-point script
  - [ ] Install instructions in README
  - [ ] Version tag and changelog

## Backlog

- [ ] **Additional Language Detectors**: Beyond the README's initial set
  - [ ] Go (`go.mod`)
  - [ ] Rust (`Cargo.toml`)
  - [ ] Elixir (`mix.exs`)
  - [ ] Java/Kotlin (`pom.xml`, `build.gradle`)
  - [ ] PHP (`composer.json`)

- [ ] **Vault Enrichment**: Nice-to-haves for the Obsidian output
  - [ ] README excerpt embedded in each project note
  - [ ] Dependency graph canvas
  - [ ] Auto-tag projects by topic (web, cli, library, app)
  - [ ] Detect monorepos and emit a parent-child relationship

- [ ] **Performance**: When scanning very large trees
  - [ ] Parallel walk with bounded concurrency
  - [ ] Cache filesystem stat calls
  - [ ] Optional `--since <date>` to skip whole subtrees

## Bugs

_No known bugs yet — project hasn't shipped. Use `# BUG:` inline tags in source to flag defects once code lands._

## Done

- [x] **Detect & Prune Orphan Notes** (2026-05-02): When a project disappears from the filesystem, its vault note becomes a stale orphan. Added `_existing_note_path` (single-line scan for `path:` in frontmatter), `_detect_orphans(vault_root)` (rglobs `*.md` and reports notes whose recorded source path no longer exists), `_prune_empty_ancestors(start, stop)` (walks up from a deleted file's parent, rmdir-ing empty dirs until non-empty or vault root), and a `--prune-orphans` CLI flag. Default behavior: report to stderr but don't touch — the vault may not be under git and deletion is destructive (poka-yoke). With the flag, orphans are deleted and any newly-empty parent dirs along the path are cleaned up so the file tree stays tidy. Verified end-to-end: scan two projects → delete one → re-scan reports the orphan + leaves it on disk → re-scan with `--prune-orphans` deletes it. Notes without a `path:` field (user-created notes, READMEs) are left strictly alone. Also cleaned up dead code from the path-mirror refactor (`_group_by_default_name` and its expanded-groups stderr block, which were stale references to the removed `_trailing_filename`).
  - [x] `_existing_note_path(note_path)` helper
  - [x] `_detect_orphans(vault_root)` walker
  - [x] `_prune_empty_ancestors(start, stop)` cleanup
  - [x] `--prune-orphans` CLI flag
  - [x] main: report always, delete + clean-up only when flag set
  - [x] Three-step test: write both → delete one → report-only → prune

- [x] **Mirror Path Ontology in Vault** (2026-05-02): Replaced the flat-filename-with-disambiguation scheme with a path-mirroring layout — each project at `<scan-root>/foo/bar/myproj` now writes to `<vault>/foo/bar/myproj.md`, so Obsidian's file tree directly reflects the source tree shape. Filename collisions are impossible by construction (paths are unique), siblings are visible by directory membership without needing wikilinks, and the MOC is redundant because the file tree IS the index. Removed: `_trailing_filename`, `_disambiguate_filenames`, `_group_by_default_name`, `_compute_siblings`, `_write_moc`, the `hashlib` import, the Siblings bullet, the MOC write call. Added: `_vault_output_path(project, scan_root, vault_root)` (handles `rel == .` for single-project scans and dots-in-dirname like `app.robotinacan.com` correctly via `f"{rel.name}.md"` rather than `with_suffix`). `emit_markdown` now takes `output_path: Path` directly; `main` mkdirs each parent on demand. Verified on `~`: 180 projects land at their full source-tree paths (e.g. three distinct `multiplex.md` files in their actual nested locations under `Documents/Projects/RobotInACan/...`); incremental scan still skips 180 on warm runs; touching a non-git project re-emits exactly that one note. Description / dependencies / VSCode link / remote bullets / parent + lang tags all preserved.

- [x] **Obsidian Markdown Emitter v1 (Description + Siblings + MOC)** (2026-05-02): Three Phase 3 enrichments shipped. (1) **Description** — `_python_metadata` and `_node_metadata` now capture the manifest's `description` field and `emit_markdown` renders it as a paragraph between H1 and bullets, giving each note real human-readable context. (2) **Sibling wikilinks** — new `_compute_siblings(projects, filenames)` groups by parent directory; each project gets a `- **Siblings**: [[a]], [[b]]` bullet linking to others in the same parent, so Obsidian draws real graph edges between sibling notes. (3) **MOC** — new `_write_moc` emits an `Index.md` at the vault root with all 180 projects grouped by parent directory under `## <parent>` headings, hub-and-spoke from a single index node. Verified end-to-end on `~`: project_finder shows its description and 13 sibling links to other `~/bin/` repos; Index.md groups across 45 parent dirs. Three follow-ups filed (per-note Structure section, incremental-scan v2 for sibling/desc changes, shared-dep wikilinks).
  - [x] Description from manifest, rendered between H1 and bullets
  - [x] Sibling wikilinks via `_compute_siblings`
  - [x] `Index.md` MOC via `_write_moc`
  - [x] Re-scanned `~` end-to-end and confirmed all three render

- [x] **Git-Aware Incremental Scan** (2026-05-02): Re-runs now skip unchanged projects. New `_project_timestamp_str(project)` helper centralizes the timestamp-string logic (git HEAD commit time → ISO; falls back to filesystem mtime for non-git projects, and `(non-git project, no mtime)` if even stat fails). New `_existing_note_timestamp(note_path)` does a single-line scan for `last_commit:` in an existing vault note. `main` precomputes the new timestamp once per project, compares it to the existing note's, and bypasses `emit_markdown` on match. `emit_markdown` was refactored to accept `timestamp_str` directly (the `ts: int | None` parameter is gone — single source of truth for the string). Output now appends "(N unchanged, skipped)" to the wrote-line. Verified: cold run writes 180, warm run skips 180, `touch` on a non-git project re-emits *just* that one, `touch` on a git project correctly does *not* re-emit (git tracks commits, not file mtime).
  - [x] `_project_timestamp_str(project)` (git + mtime fallback)
  - [x] `_existing_note_timestamp(note_path)` reader
  - [x] `emit_markdown` refactored: takes `timestamp_str` directly
  - [x] `main` loop: compare new vs. existing, skip on match
  - [x] "(N unchanged, skipped)" in output
  - [x] Cold/warm/touch-non-git/touch-git tests all behave correctly

- [x] **Project Metadata Extraction v1 (Python + Node)** (2026-05-02): Notes now carry manifest-derived metadata when parseable. `pyproject.toml` (PEP 621 `[project]` table, parsed with stdlib `tomllib`) and `package.json` (parsed with `json`) feed `package_name` / `package_version` into frontmatter and a truncated `Dependencies (N)` bullet into the body. Bumped `requires-python` to `>=3.11` for `tomllib`. `extract_metadata` orchestrator returns the first non-None result (Python checked first), so polyglot projects pick one source per note for now. Verified end-to-end: `project_finder` shows its own pyproject metadata; `claude-max-api-proxy` shows `package_name: claude-max-api-proxy / version: 1.0.0 / Dependencies (2): express, uuid`; full `~` scan succeeds on 180 projects with zero crashes (86 notes have `package_name`, 61 have a Dependencies bullet). Other manifests (Gemfile, Package.swift, configure, DESCRIPTION) and filesystem-mtime fallback are filed as follow-ups.
  - [x] Bumped `requires-python` to `>=3.11`
  - [x] `_python_metadata(repo)` and `_node_metadata(repo)`
  - [x] `extract_metadata(repo)` orchestrator
  - [x] `emit_markdown` adds conditional `package_name` / `package_version` frontmatter
  - [x] `emit_markdown` adds truncated `Dependencies (N)` bullet
  - [x] Smoke-tested project_finder, a Node project, full `~` scan

- [x] **External Excludes File** (2026-05-02): User-supplied exclude-dir names now layer on top of the hardcoded `EXCLUDED_DIR_NAMES` baseline, from two sources: an auto-loaded `<scan-path>/.project_finder_exclude` (best-effort — missing file is silently ignored) and a `--exclude-from <FILE>` CLI flag. File format is one dir name per line, with `#` comments and blanks tolerated. Threaded through `find_projects` via a new `extra_excludes` parameter. The "Found N projects" line now appends `(+N extra exclude(s))` when user excludes are in play, so the layering is transparent. Verified end-to-end with both file-based and flag-based input on a constructed `keep-me`/`skip-me` tree.
  - [x] `_load_excludes(path) -> frozenset[str]` helper (silent on missing)
  - [x] `--exclude-from FILE` CLI flag
  - [x] Auto-load `<scan-path>/.project_finder_exclude`
  - [x] `find_projects` accepts and merges `extra_excludes`
  - [x] Tested via `.project_finder_exclude` and `--exclude-from`

- [x] **Smart C Detection** (2026-05-02): Restored Makefile-driven C project detection without re-introducing the `~/bin/Makefile` false positive. Added `C_SOURCE_EXTENSIONS` constant and `_is_smart_c_project(files)` helper that requires a `Makefile` *plus* at least one `.c` / `.h` / `.cpp` / `.cc` / `.cxx` / `.hpp` / `.hxx` sibling at the same level. Wired into both `find_projects` (Makefile+C-source dirs are detected as projects) and `detect_languages` (those projects get `lang/c`). Verified: a constructed `Makefile+main.c` dir is detected and tagged; a Makefile-only dir is NOT claimed (`~/bin` stays at 14 projects). Scanning `~` rose from 170 → 180 — the 10 new projects are real Arduino-bootloader-style Makefile+C dirs, and 12 notes now carry the `lang/c` tag.
  - [x] `C_SOURCE_EXTENSIONS` constant + `_is_smart_c_project(files)` helper
  - [x] `find_projects` OR-in `_is_smart_c_project(files)`
  - [x] `detect_languages` listdir + smart-C path
  - [x] Constructed Makefile+main.c → detected + tagged `lang/c`
  - [x] `~/bin/Makefile` alone → not claimed (regression safe)
  - [x] `~` scan: 170 → 180 (10 real new C projects, no false positives)

- [x] **Disambiguate Filename Collisions v2** (2026-05-02): Replaced the post-write collision *warning* with mechanical uniqueness *by construction*. New `_trailing_filename(project, n)` builds names from the last *n* meaningful path components; `_disambiguate_filenames(projects)` runs over the full project list once and expands trailing-segment count per colliding group until every member is unique (with a SHA-1 fallback for the effectively-impossible case). `main()` now precomputes all filenames before any write happens — silent overwrites are structurally impossible. Verified on `~`: 170 projects → 170 unique files, with the three `plugin/multiplex` paths cleanly resolved as `guidebook_plugin_multiplex.md`, `tutorials_plugin_multiplex.md`, `mess_experiment_plugin_multiplex.md`. The runtime warning was replaced with an informational stderr note showing what was disambiguated and to what.
  - [x] Add `_trailing_filename(project, n)`
  - [x] Add `_disambiguate_filenames(projects)` with segment-expansion + hash fallback
  - [x] Update `emit_markdown` to accept a precomputed filename
  - [x] Update `main()` to call disambiguation up front; informational note replaces warning
  - [x] Re-run `~` scan and confirm 170 unique files

- [x] **Skip Hidden Dirs by Default (Poka-Yoke)** (2026-05-02): Walking `~` blew up at first attempt — `~/.bun`, `~/.cache`, `~/.npm`, `~/.cargo`, `~/.pyenv`, `~/.local`, `~/.rustup` all contain tool-managed cached packages with `package.json` / `pyproject.toml` / `Gemfile` markers, each falsely marked as a project. Fix: `find_projects` now prunes any dir whose name starts with `.` by default (matches the `find`/`ls` convention), with `--include-hidden` to opt back in. Also added `Caches`, `Containers`, `Application Support` to `EXCLUDED_DIR_NAMES` to catch macOS `~/Library/...` traps. As a related poka-yoke, the runtime now detects `<parent>_<name>` filename collisions and warns to stderr with the colliding paths — found 170 projects in `~`, with one 3-way `plugin_multiplex.md` collision visibly reported (deeper rename scheme deferred to a follow-up card).
  - [x] Prune dirs starting with `.` in `find_projects`
  - [x] Add `--include-hidden` CLI flag
  - [x] Add macOS Library noise to `EXCLUDED_DIR_NAMES`
  - [x] Update module docstring + `--help` so the hidden-skip is discoverable
  - [x] Re-scan `~` end-to-end (170 projects, sane count, collision warning surfaces)
  - [x] Bonus: runtime collision detection + stderr warning

- [x] **Project Discovery Walker** (2026-05-02): Replaced `find_git_repos` with `os.walk`-based `find_projects` that detects any project root by marker (git or language file), stops descending once a root is identified, and prunes common noise dirs (`node_modules`, `__pycache__`, `.venv`, `venv`, `target`, `build`, `dist`, `vendor`, plus the `.mypy_cache` / `.pytest_cache` / `.ruff_cache` trio). `emit_markdown` now degrades gracefully for non-git projects (no `git` tag, no Remote bullet, no Last-commit bullet, frontmatter timestamp says `(non-git project)`). Verified on `~/bin/` (still 14) and a constructed mixed tree exercising git, non-git, nested, monorepo-stop-descent, and `node_modules` pruning.
  - [x] Replace `find_git_repos` with `find_projects` (os.walk + unified `PROJECT_MARKERS`)
  - [x] Stop descending once a project root is identified
  - [x] Hardcoded excluded-dir list (CSV-loading deferred to a Prototype Follow-up)
  - [x] `emit_markdown` gracefully degrades for non-git projects
  - [x] Smoke tested on `~/bin/` and a mixed synthetic tree

- [x] **Vault Note Enrichment v1** (2026-05-02): Each note now carries a `parent/<dir>` tag, one `lang/<name>` tag per detected language (python, node, ruby, swift, perl, c, r — by marker files in the repo root), and a `- **Remote**: <url>` bullet linking to the host repo (SSH→HTTPS normalized, `.git` stripped). All bullets degrade gracefully when their data is absent.
  - [x] Add host repo link (`git remote get-url origin`, SSH→HTTPS, strip `.git`)
  - [x] Add `parent/<dir>` tag from the repo's containing directory
  - [x] Detect languages from root marker files and emit `lang/<name>` tags
  - [x] Re-run on `~/bin/` and confirm tags + host links render correctly

- [x] **Disambiguate Repo Filenames + VSCode Links** (2026-05-02): Filenames now `<parent>_<repo>.md` (e.g. `bin_project_finder.md`); path bullet is a `vscode://file//<abs-path>` link. Verified with a constructed two-`notes` collision tree and a re-run on `~/bin/`.
  - [x] Decide naming scheme — `<parent-dir>_<repo-name>.md`
  - [x] Update `emit_markdown` in `src/project_finder/cli.py` to use the chosen scheme
  - [x] Make the path bullet a `vscode://file/<abs-path>` link
  - [x] Test on a tree with two repos sharing a basename to confirm no overwrites

- [x] **Smallest Prototype** (2026-05-02): Walk tree, find dirs containing `.git`, emit one markdown per repo with path + last commit timestamp. Python, stdlib only. Verified on 14 repos in `~/bin/`.
  - [x] Initialize repo as a git project (`git init`)
  - [x] Add license file (AGPL per README)
  - [x] Set up dependency manifest and entry point matching `project_finder <scan-path> [vault-output-path]`
  - [x] Run end-to-end on a real tree and confirm the output looks right

- [x] **TodoScope Alignment** (2026-05-02): Bootstrap repo for kanban scanning
  - [x] Create `.todoscope-exclude.csv` with sensible defaults
  - [x] Create initial `TODO.md` with convention header and roadmap structure
