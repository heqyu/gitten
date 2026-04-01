# gitten 🐱

A terminal UI for browsing and managing git history.

## Install

```bash
pip install -e .
```

## Usage

```bash
gitten              # current directory
gitten /path/to/repo
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑↓` / `j k` | Navigate commits |
| `Enter` | View file diff |
| `m` / right-click | Context menu |
| `[` | Toggle branch panel |
| `c` | Copy commit log |
| `r` | Refresh |
| `?` | Help |
| `q` | Quit |

## Operations (via context menu)

- **Revert** — create a reverse commit
- **Drop** — delete an unpushed commit
- **Squash** — merge all unpushed commits into one
- **Push to remote** — push current branch
- **Cherry-pick** — apply a commit from another branch
