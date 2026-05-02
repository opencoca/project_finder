This is a clean and simple huristic harness that locates dev projects in given folder and generates a single intelligent Obsidian documentation vault for them. It scans project directories, creates interlinked markdown notes with hardlinks to source files, and intelligently detects changes using git metadata to avoid expensive rescans.

## Features

- **Automatic Project Discovery** — Recursively locates development projects (git repos, Node.js, Python, Ruby. Swift, Perl, C, R etc.) in any folder
- **Obsidian Vault Generation** — Creates beautifully structured markdown documentation with bidirectional links in obsidinas markdown wiki style with clear tagged front matter
- **Smart Change Detection** — Leverages git history to identify only modified projects, skipping unchanged ones
- **Hardlinked References** — Maintains direct filesystem links between documentation and source code
- **Elegant Architecture** — Simple, fast heuristics-based scanning without heavy databases

## Usage

```bash
project_finder <scan-path> [vault-output-path]
```

## How It Works

1. **Scan Phase** — Walks the directory tree identifying projects by common markers (`.git`, `package.json`, `pyproject.toml`, etc.)
2. **Change Detection** — For each project, checks git commit timestamps against the vault to determine if a rescan is needed
3. **Documentation Generation** — Creates project-specific markdown files with project metadata, dependencies, and structure
4. **Linking** — Auto-generates Obsidian-compatible links between related projects and hardlinks to source directories
5. **Update Phase** — On subsequent runs, only rescans modified projects

## Benefits

- Fast incremental updates thanks to git-aware change detection
- Beautiful, discoverable documentation in your favorite note-taking app
- Always-fresh project landscape without manual maintenance


Licence AGPL.

Created by Alex Somma of Startr 