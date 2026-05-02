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

### Phase 1 — Scan

- [ ] **Project Discovery Walker**: Recursively find projects by marker files
  - [ ] Walk directory tree honoring `.todoscope-exclude.csv` style exclusions
  - [ ] Detect git repos via `.git`
  - [ ] Detect Node.js via `package.json`
  - [ ] Detect Python via `pyproject.toml`, `setup.py`, `requirements.txt`
  - [ ] Detect Ruby via `Gemfile`
  - [ ] Detect Swift via `Package.swift`
  - [ ] Detect Perl via `Makefile.PL`, `cpanfile`
  - [ ] Detect C via `Makefile`, `configure`, `CMakeLists.txt`
  - [ ] Detect R via `DESCRIPTION`
  - [ ] Stop descending once a project root is identified (don't double-count subprojects)

- [ ] **Project Metadata Extraction**: Read what each marker tells us
  - [ ] Extract name, version, dependencies from each manifest type
  - [ ] Capture project root path and detected language(s)
  - [ ] Capture last-modified timestamp from filesystem and git

### Phase 2 — Change Detection

- [ ] **Git-Aware Incremental Scan**: Skip unchanged projects
  - [ ] Read each project's latest commit timestamp
  - [ ] Compare against vault's recorded timestamp for that project
  - [ ] Mark projects as fresh / stale / new
  - [ ] Fall back to filesystem mtime for non-git projects

### Phase 3 — Vault Generation

- [ ] **Obsidian Markdown Emitter**: Produce one note per project
  - [ ] Front matter with tags (language, has-git, last-updated)
  - [ ] Project description, dependencies, structure
  - [ ] Wiki-style `[[links]]` between related projects (shared deps, sibling repos)
  - [ ] Index/MOC note that lists all projects

- [ ] **Hardlinked Source References**: Filesystem links from vault to source
  - [ ] Detect existing hardlink count before writing (preserve inode if present)
  - [ ] Create hardlinks (not symlinks) from vault into project source dirs
  - [ ] Handle cross-filesystem case gracefully (warn, fall back to symlink or skip)

### Phase 4 — Update & Maintenance

- [ ] **Idempotent Re-runs**: Subsequent runs only touch changed projects
  - [ ] Persist a small state file in the vault (project → last-scanned commit)
  - [ ] On re-run, diff state vs. current and only regenerate stale notes
  - [ ] Detect deleted projects and prune their notes

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
