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

## Backlog

### Active: Two-Writer Workflow

- [ ] **M1 — Shadow tree for merge base**: Add `.project-finder/last-auto/<rel>/<note>.md` shadow mirror of the vault. After every successful emit, atomically write the freshly generated content to the shadow alongside writing it to the live file. The shadow is the `base` argument for 3-way merge on the next scan.
  - [ ] Add `_shadow_path(output_path, vault_root)` helper computing the parallel path under `.project-finder/last-auto/`
  - [ ] After each successful emit, write the same content to the shadow path (mkdir parent on demand)
  - [ ] Atomic write via tempfile + rename so a crash mid-emit doesn't leave the shadow stale
  - [ ] Test: cold scan, verify shadow tree mirrors vault structure 1:1
  - [ ] Test: re-scan after editing a project, verify shadow updates with the new content

- [ ] **M2 — 3-way merge via `git merge-file` in `emit_markdown`**: When the live file already exists, read it, read the shadow as `base`, treat the new auto content as `ours`, the live file as `theirs`. Shell out to `git merge-file --stdout ours base theirs` and write the result. Conflict markers (`<<<<<<<` etc.) land in the file when both sides edit the same line.
  - [ ] Add `_three_way_merge(base, ours, theirs) -> tuple[str, bool]` helper using `git merge-file --stdout`; second tuple value is `has_conflicts`
  - [ ] In `main` loop, when both `output_path` and shadow exist, call merge instead of direct write
  - [ ] Fall back to direct write when shadow is missing (first run after migration) or when output_path doesn't exist
  - [ ] Track per-file outcome (clean vs. conflict) and pass to M4's logger
  - [ ] Test: synthetic non-conflicting modification on both sides → merge cleanly
  - [ ] Test: synthetic same-line conflict → conflict markers land in file, outcome=conflict

- [ ] **M3 — Layer 2 structural resolvers (≈5 hardcoded patterns)**: After M2 produces a conflict, walk each conflict hunk and try the resolvers in order before giving up. Patterns: (1) tag-list union, (2) bullet-list both-append, (3) frontmatter scalar where exactly one side matches base, (4) whitespace-only divergence (take theirs), (5) identical-after-normalization. Each resolver is a plain Python function in cli.py.
  - [ ] Add `_parse_conflict_hunks(text)` helper extracting `<<<<<<< / ======= / >>>>>>>` regions
  - [ ] Implement `_resolve_tag_list_union(hunk)` — both sides modified `tags: [...]` → union
  - [ ] Implement `_resolve_bullet_list_append(hunk)` — both sides added different bullets → concat
  - [ ] Implement `_resolve_frontmatter_scalar(hunk)` — exactly one side matches base → take the other
  - [ ] Implement `_resolve_whitespace_only(hunk)` — only whitespace differs → take theirs
  - [ ] Implement `_resolve_identical_after_normalization(hunk)` — collapse trailing-newline / quote-style differences
  - [ ] Add orchestrator `_apply_layer2(merged_text)` that walks hunks, tries resolvers in order, returns resolved text + list of resolver names applied
  - [ ] Wire into M2's post-merge flow: when conflicts exist, run Layer 2 before declaring `outcome=conflict`
  - [ ] Test each resolver in isolation with synthetic conflict input
  - [ ] Test orchestrator end-to-end with mixed conflict types

- [ ] **M4 — Logfmt merge audit log + end-of-scan summary**: Append one logfmt line per merge to `.project-finder/merge-audit.log` (`ts= file= outcome=clean|layer2|conflict resolver=`). At the end of the scan, print an stderr summary: `N clean, M layer2-resolved, K need-manual` plus the file list of K. Outcome=conflict is the only one that asks the user to do something.
  - [ ] Add `_audit_log(vault_root, **fields)` helper appending one logfmt line to `.project-finder/merge-audit.log`
  - [ ] Quote values containing spaces (`rationale="kept user annotation"`)
  - [ ] Track aggregate counts in `main`: clean / layer2-resolved / need-manual
  - [ ] After loop, print stderr summary: `Merged: N clean, M layer2-resolved, K need-manual`
  - [ ] If K > 0, list affected file paths to stderr (relative to vault_root)
  - [ ] Test: scan with mixed outcomes, verify log lines + summary numbers match

- [ ] **I1 — SilverBullet setup**: `docker run -p 3000:3000 -v <vault>:/space silverbullet`, document workflow in README. Includes a Space Lua snippet for querying notes by `lang/<x>` tag as a starter dashboard.
  - [ ] Document docker run command + workflow in README under `## SilverBullet`
  - [ ] Write a starter Space Lua dashboard snippet (query notes by `lang/<x>`, list by parent)
  - [ ] Save the snippet as a `Dashboards.md` note (or document where the user pastes it)
  - [ ] Verify SilverBullet loads the live vault, the dashboard renders, and queries return data

- [ ] **I2 — Quartz wiring**: clone Quartz, symlink `content/ -> <vault>`, document `npx quartz build --serve` for local preview and `quartz build` + deploy for publish. Include the `vscode://` URL allowlist tweak.
  - [ ] Document Quartz setup in README under `## Quartz` (clone, symlink content/, install deps)
  - [ ] Identify and document the Quartz config tweak for allowlisting `vscode://` URLs
  - [ ] Run `npx quartz build --serve` locally and verify rendering on http://localhost:8080
  - [ ] Document at least one concrete deploy recipe (GitHub Pages / Netlify / Vercel)

- [ ] **I3 — `publish: false` frontmatter convention**: project_finder respects an existing `publish: false` field in user-edited content (don't overwrite). Document it for Quartz config so private notes stay out of the static site.
  - [ ] Update `emit_markdown` to detect a `publish:` field in the existing note and preserve its value
  - [ ] Document the convention in README (how to mark a note private)
  - [ ] Document the matching Quartz config to filter on `publish: false`
  - [ ] Test: manually add `publish: false` to a note, re-scan, verify the field is preserved

- [ ] **I4 — Optional vault-as-git auto-commit**: `--commit` flag that does `git add . && git commit -m "auto: scan completed at <ts>"` after writes (skips if no changes, no-op if vault isn't a git repo). Recovery layer; orthogonal to the merge subsystem.
  - [ ] Add `--commit` CLI flag
  - [ ] Add `_auto_commit(vault_root, message) -> bool` helper (returns True if a commit happened)
  - [ ] Skip cleanly when vault is not a git repo OR no changes are pending
  - [ ] Wire into `main` after the merge loop, conditional on flag
  - [ ] Test: vault is git repo, dirty after scan, `--commit` → verify commit
  - [ ] Test: vault not a git repo, `--commit` → graceful no-op
  - [ ] Test: vault clean, `--commit` → no empty commit

### LLM (deferred until Layer 1+2 residual rate is observed)

- [ ] **L3a — LLM-assisted suggestion for residual conflicts**: For conflicts that survive M3, send (base, ours, theirs) to an LLM (Anthropic API behind a clean adapter), attach the suggestion as an HTML comment below the conflict block. Suggestion-only — never silent application. Includes content-derivability validation (suggestion's words must be derivable from the three inputs).
  - [ ] Add Anthropic SDK dependency (claude-haiku for cost efficiency)
  - [ ] Define `LLMAdapter` protocol; default impl = Anthropic API
  - [ ] Add prompt template (base, ours, theirs → suggestion + confidence + rationale)
  - [ ] Add `_validate_suggestion(suggestion, base, ours, theirs)` — content-derivability check (≥95% words from inputs)
  - [ ] On conflict survival (after Layer 2), call adapter, validate, attach as `<!-- pf-llm-suggestion -->` comment below the conflict block
  - [ ] Add per-scan call cap (default 20) + stderr warning when reached
  - [ ] Test: synthetic conflict the LLM should handle → suggestion attached
  - [ ] Test: malformed LLM output → graceful fallback to raw conflict, audit log records the failure

- [ ] **L3b — Hash-based LLM cache** at `.project-finder/llm-cache/` keyed by `sha256(base, ours, theirs)`.
  - [ ] Create `.project-finder/llm-cache/<sha256>.json` cache layer
  - [ ] Cache key = `sha256(base + ours + theirs)`
  - [ ] Cache value = full LLM response (suggestion, confidence, rationale)
  - [ ] Wire as a check before LLM call in L3a
  - [ ] Test: same conflict twice → second call hits cache, no LLM call

- [ ] **L3c — `--auto-resolve <high|medium|low>` flag** to apply LLM suggestions directly when confidence ≥ threshold, wrapped in `<!-- pf-llm-resolved -->` markers for audit.
  - [ ] Add `--auto-resolve <high|medium|low>` flag (off by default)
  - [ ] When set, apply LLM suggestions whose confidence ≥ threshold inline, wrapped in `<!-- pf-llm-resolved -->` markers
  - [ ] Log auto-applied resolutions to merge-audit.log with confidence + threshold
  - [ ] Test: low-threshold scan applies high+medium+low; high-threshold applies only high; conflicts below threshold remain raw

### Carry-overs

- [ ] **Project Note Structure**: Add a per-note `## Structure` section listing the project's top-level files and immediate subdirs (skipping `.git`, `__pycache__`, etc.). Useful for at-a-glance "what does this project look like" without leaving Obsidian. Keep it shallow — full tree is overwhelming.
  - [ ] Add `_project_structure(project, max_entries=20)` returning top-level files + dirs (filter via `EXCLUDED_DIR_NAMES` + dotdir rule)
  - [ ] Render result as a `## Structure` heading + bullet list in the note body
  - [ ] Cap at top-level only (no recursion); show "+N more" if more than `max_entries`
  - [ ] Test on project_finder itself: should list LICENSE, README.md, TODO.md, pyproject.toml, src/, etc.

- [ ] **Re-emit on Description Change (Incremental Scan v2)**: Current incremental scan compares only `last_commit:`. If a manifest's `description` changes without a commit moving, the existing note stays stale. Possible fix: extend the comparison to a hash of `(timestamp + description)` stored in frontmatter, or add a `--force-rebuild` flag.
  - [ ] Decide approach: content hash in frontmatter (auto-detect), `--force-rebuild` flag (manual override), or both
  - [ ] Implement chosen approach in `main`'s incremental-skip logic
  - [ ] Document the behavior in README / `--help`
  - [ ] Test: change a manifest description, re-scan, verify note re-emits
  - [ ] Test: no source change, re-scan, verify note still skipped

### Brand Move (gated on Startr trademark filing)

- [ ] **Rename project_finder → Startr Repo Radar**: Brand consolidation under the Startr umbrella, alongside TodoScope. Gated on filing the "Startr" word-mark trademark application (US Classes 9 + 42 minimum) — the rename commits the project to the brand name, and Apple's Mac App Store has an existing "Repo Radar" by Callum Matthews (Sept 2025, 0 ratings, indie), so a registered Startr house mark materially strengthens any future "Startr Repo Radar.app" submission against confusing-similarity grounds. Naming canonicalization decided: brand "Startr Repo Radar"; PyPI distribution `reporadar`; Python import package `reporadar` (one word — matches CLI, since `repo_radar`/`repo-radar` is taken on PyPI); CLI command `reporadar`; config file `.reporadar_exclude` (clean break, no backward-compat — pre-1.0). See the 2026-05-03 plan-out for full file-by-file detail.

  Pre-filing (you book outside this repo) — [MANUALLY]:
  - [ ] Knock-out search "STARTR" at [tmsearch.uspto.gov](https://tmsearch.uspto.gov) — Classes 9 + 42, plus phonetic variants
  - [ ] Get 2–3 flat-fee quotes from US trademark attorneys (~$750–$1,500 attorney + $500–$700 USPTO fees for two classes; total ~$1,500–$2,200)
  - [ ] (Optional) CIPO knock-out + Canadian filing if Startr has CA presence (+~$1,300–$2,000 CAD all-in)
  - [ ] File US "STARTR" word-mark application, Classes 9 + 42, "intent to use" (1B) basis
  - [ ] Calendar §8 declaration window (year 5–6) + §8+§9 renewal window (year 9–10) the day the cert arrives

  Repo rename (unblocks once filing is submitted) — split [WE] / [MANUALLY]:
  - [ ] [WE] `git mv src/project_finder src/reporadar`
  - [ ] [WE] [pyproject.toml](pyproject.toml): `name = "reporadar"`, `[project.scripts] reporadar = "reporadar.cli:main"`, `packages = ["src/reporadar"]`
  - [ ] [WE] [src/reporadar/cli.py](src/project_finder/cli.py): module docstring → "Startr Repo Radar — …"; `prog="reporadar"`; replace every `.project_finder_exclude` with `.reporadar_exclude` (4 occurrences); update help-text "project_finder" mentions
  - [ ] [WE] [src/reporadar/__init__.py](src/project_finder/__init__.py): docstring update
  - [ ] [WE] [README.md](README.md): title → "Startr Repo Radar", install commands `uv tool install .` then `reporadar` (drop `project_finder`); `python -m reporadar.cli`; tagline / blurb mentions "Startr"
  - [ ] [WE] [CHANGELOG.md](CHANGELOG.md): new `## [0.2.0] - <date> (unreleased)` entry under `### Changed` — "Renamed package + CLI to `reporadar`; brand is Startr Repo Radar; config file convention `.project_finder_exclude` → `.reporadar_exclude` (clean break, pre-1.0)"; update version-tag URL footer
  - [ ] [WE] [TODO.md](TODO.md): header `# TODO — Startr Repo Radar`; replace `project_finder` mentions in body where current (Done entries are historical, leave alone)
  - [ ] [WE] `pyproject.toml` version bump → `0.2.0`; `__init__.py` `__version__` synced
  - [ ] [WE] Regenerate [uv.lock](uv.lock) via `uv lock`
  - [ ] [WE] Sweep: `grep -rn "project_finder\|project-finder" --include="*.py" --include="*.toml" --include="*.md"` should return zero hits in source (Done-column historical refs in TODO/CHANGELOG are fine)
  - [ ] [MANUALLY] Close any shells/agents cwd'd in `~/bin/project_finder`, then `mv ~/bin/project_finder ~/bin/repo_radar` (or `~/bin/reporadar` — pick one)
  - [ ] [MANUALLY] GitHub: rename remote repo in settings (`project_finder` → `reporadar`); `git remote set-url origin git@github.com:sommaalexander/reporadar.git`
  - [ ] [MANUALLY] `uv tool uninstall project_finder && uv tool install ~/bin/repo_radar` (or whatever the new dir is)
  - [ ] [WE] Verify: `which reporadar`; `reporadar --help` shows new prog; `reporadar ~ ~/Obsidian/project-finder-test` runs cleanly (consider also renaming the test vault to `reporadar-test` if you want consistency)
  - [ ] [MANUALLY] `git tag -a v0.2.0 -m "Renamed to Startr Repo Radar"` && `git push --tags`

## TODO

### Other roadmap

- [ ] **Hardlinked Source References**: Filesystem links from vault to source — `ln` (not symlink) from a representative source file (likely each project's README) into the vault note's directory, so opening the note in Obsidian gives instant access to the source README. Detect existing hardlink count before writing (preserve inode if present); handle cross-filesystem case gracefully (warn, fall back to symlink or skip).
  - [ ] Decide which file to hardlink (per-project README is the obvious starting point)
  - [ ] Add `_hardlink_source(project, output_dir)` helper
  - [ ] Detect existing hardlink count before writing — preserve inode if file is already hardlinked
  - [ ] Use `os.link` (hardlink, not symlink) within same filesystem
  - [ ] Handle cross-filesystem case: warn, fall back to symlink or skip per a flag
  - [ ] Test: project with README → vault gets hardlinked README, modifying one updates both
  - [ ] Test: project without README → graceful no-op
  - [ ] Test: re-run with hardlink already in place → preserves the existing inode

### Pre-Release

- [ ] **Test Harness**: Cover the scanner and emitter
  - [ ] Fixture directory with one project of each supported language
  - [ ] Snapshot tests for emitted markdown
  - [ ] Test incremental re-run skips unchanged projects

### Enhancements

- [ ] **Vault Enrichment**: Nice-to-haves for the Obsidian output
  - [ ] README excerpt embedded in each project note
  - [ ] Dependency graph canvas
  - [ ] Auto-tag projects by topic (web, cli, library, app)
  - [ ] Detect monorepos and emit a parent-child relationship

- [ ] **Additional Language Detectors**: Beyond the README's initial set
  - [ ] Go (`go.mod`)
  - [ ] Rust (`Cargo.toml`)
  - [ ] Elixir (`mix.exs`)
  - [ ] Java/Kotlin (`pom.xml`, `build.gradle`)
  - [ ] PHP (`composer.json`)

- [ ] **Performance**: When scanning very large trees
  - [ ] Parallel walk with bounded concurrency
  - [ ] Cache filesystem stat calls
  - [ ] Optional `--since <date>` to skip whole subtrees

## Bugs

_No known bugs yet — project hasn't shipped. Use `# BUG:` inline tags in source to flag defects once code lands._

## Done

- [x] **Packaging & Install** (2026-05-03): Closed out the v1-readiness card. The `[project.scripts]` entry in `pyproject.toml` already puts `project_finder` on PATH after install, so no separate shebang/entry-point script was needed. Added an `## Installation` section to README documenting the three practical paths: `uv tool install .` (global), `uv run project_finder ...` (one-off), and `python -m project_finder.cli ...` (in-checkout dev). Created `CHANGELOG.md` in Keep-a-Changelog format with a `[0.1.0] - 2026-05-03 (unreleased)` section summarizing every shipped Done card grouped under Added / Tools. Tagging `v0.1.0` is a [MANUALLY] release act left for Alex to run when ready (`git tag -a v0.1.0 -m "..." && git push --tags`).
  - [x] Shebang / entry-point script — already in place via `[project.scripts]`, verified
  - [x] Install instructions in README — `## Installation` section between `## Features` and `## Usage`
  - [x] Version tag and changelog — `CHANGELOG.md` written; `git tag v0.1.0` is [MANUALLY], your call

- [x] **CLI Polish** (2026-05-03): Closed out the first-run UX card. Three of four subtasks were already shipped during prior cards (argparse with full help strings on every flag, `Path.cwd() / "vault"` default for vault-output-path, per-project + summary progress lines). The fourth — exit codes for partial failures — was the real gap: a single corrupt project crashed the entire scan, dropping all subsequent emits. Fixed by wrapping the per-project loop body in `try/except Exception`: failures log a `! <path>: <exception>` line to stderr, increment a `failed` counter, and the loop continues. After the loop, if `failed > 0`, the process raises `SystemExit(1)` with a summary line. Verified with a synthetic test (booby-trapped vault with a file blocking a needed directory): bad project failed cleanly with stderr message, good project still emitted, exit code 1. Re-ran on `~` against the live vault: 177 unchanged-skipped + 3 re-emitted, exit code 0. No regressions.
  - [x] `--help` with usage and flag list — already in place via argparse
  - [x] Sensible default for `vault-output-path` if omitted — already in place (`Path.cwd() / "vault"`)
  - [x] Progress output during scan — already in place (per-project + summary lines)
  - [x] Exit codes for partial failures — `try/except Exception` per project, `SystemExit(1)` if any failed

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
