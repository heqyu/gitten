# gitten — Git TUI Tool Design

**Date:** 2026-04-01

## Overview

`gitten` is a terminal-based git log viewer and action tool built with Python and Textual. It provides a three-panel TUI for browsing commits across branches, filtering by author, viewing diffs, and performing common git operations without leaving the terminal.

## Tech Stack

- **Python 3.11+**
- **textual** — TUI framework (layout, components, mouse/keyboard interaction)
- **gitpython** — git repository access and operations
- **pyperclip** — clipboard support for copying commit logs and hashes

## Startup

```bash
gitten              # uses current working directory
gitten /path/to/repo
```

On startup, the repo path is validated. If not a valid git repository, an error message is shown and the tool exits.

## Project Structure

```
gitten/
├── main.py              # Entry point, CLI argument parsing
├── app.py               # Textual App main class, layout composition
├── git_service.py       # All git operations (queries, cherry-pick, revert, etc.)
├── components/
│   ├── branch_panel.py  # Left panel: branch selector + commit list
│   ├── commit_panel.py  # Middle panel: current branch commit list
│   ├── detail_panel.py  # Right panel: commit detail + file change list
│   └── diff_modal.py    # Full-screen modal: file diff viewer
└── styles.tcss          # Textual CSS styles
```

## Layout

Three-panel layout:

```
┌──┬────────────────────────────┬───────────────────────┐
│  │ main (current)             │ Detail                │
│≡ │ Author: [current user   ]  │                       │
│  │ ─────────────────────────  │  commit: a1b2c3d      │
│  │▶ a1b2c3 fix bug        3h  │  Author: xxx          │
│  │  f3e2d1 add feat       1d  │  Date:   2026-04-01   │
│  │  b2c1a0 init           3d  │  Message:             │
│  │                            │    fix: correct the   │
│  │                            │    null pointer issue │
│  │                            │                       │
│  │                            │  Changes:             │
│  │                            │  > src/main.py        │
│  │                            │  > tests/test_main.py │
│  │                            │                       │
│  │                            │  [c] Copy log         │
└──┴────────────────────────────┴───────────────────────┘
```

### Left Panel (collapsible)

- **Default state:** collapsed to a narrow strip showing only a toggle icon (`≡`)
- **Toggle:** `[` key or click the strip to expand/collapse
- **Expanded contents:**
  - Branch selector: dropdown with search/filter input, lists all local and remote branches
  - Author filter input box
  - Commit list for the selected branch (single-line per commit)
- Selecting a branch refreshes the commit list below it

### Middle Panel (current local branch)

- Always visible
- Header shows current branch name
- Author filter input box, pre-filled with current git user (`git config user.name`), clearable to show all
- Single-line commit rows: `hash | message | author | relative time`
- **Unpushed commits** highlighted with yellow background
- Currently selected row highlighted in blue

### Right Panel (detail)

- Always visible
- Displays on commit selection:
  - Full commit hash
  - Author + date
  - Full commit message
  - List of changed files (prefixed with `>`)
- `c` key copies the full commit log to clipboard
- `Enter` on a selected file opens the diff modal

### Diff Modal

- Full-screen modal overlay
- Shows unified diff for the selected file
- Added lines in green, removed lines in red, line numbers shown
- `↑↓` / `j k` to scroll
- `n` / `p` to navigate between changed files in the same commit
- `Esc` to close and return to detail panel

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑↓` / `j k` | Move selection up/down |
| `Enter` | Open diff for selected file |
| `m` or right-click | Open context menu for selected commit |
| `[` | Toggle left panel expand/collapse |
| `c` | Copy commit log to clipboard |
| `r` | Manual refresh |
| `q` | Quit |
| `?` | Show help panel |
| `Esc` | Close modal / cancel |

## Context Menus

Triggered by right-click or `m` key on a selected commit row. Menu items are shown/hidden based on commit state.

### Middle Panel (current branch commits)

| Action | Available when | Description |
|--------|---------------|-------------|
| **Revert** | Any commit | Creates a new reverse commit |
| **Drop** | Unpushed only | Removes commit from history via rebase |
| **Squash** | Unpushed only | Squashes this commit and all preceding unpushed commits into one |
| **Push to remote** | Branch has a remote tracking branch | Pushes to remote; shows error on conflict |
| **Copy hash** | Any commit | Copies commit hash to clipboard |

### Left Panel (other branch commits)

| Action | Available when | Description |
|--------|---------------|-------------|
| **Cherry-pick** | Any commit | Applies commit to current local branch |
| **Copy hash** | Any commit | Copies commit hash to clipboard |

## Operation Result Handling

- **Success:** Status bar briefly shows a green success message; commit list auto-refreshes
- **Failure / conflict:** Error modal displays the raw git error output; conflict-type operations (cherry-pick, revert) include an "Abort" button that runs the appropriate `--abort` command
- No confirmation dialogs — operations execute immediately

## Color Scheme

| Element | Style |
|---------|-------|
| Unpushed commits | Yellow background |
| Selected row | Blue highlight |
| Current branch indicator | `●` prefix in left panel |
| Diff added lines | Green |
| Diff removed lines | Red |
| Success messages | Green text in status bar |
| Error messages | Red text / modal |

## Data Refresh

- **On startup:** Full refresh of all commit data
- **Manual:** `r` key triggers immediate refresh
- **Auto:** Background refresh every 1 hour
