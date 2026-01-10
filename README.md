# NotebookLM Skill for Claude Code

A Claude Code skill for automating Google NotebookLM through browser automation (Playwright).

## Features

- **Notebook Management**: List, create, delete notebooks
- **Source Management**: List sources, upload documents, search & import web sources
- **Smart Chat**: Chat with notebooks, auto-save responses as notes
- **Audio Generation**: Generate podcast audio from notebooks
- **State Management**: Handle search state machine (READY/PENDING_RESULTS)
- **Cross-platform**: Supports Chrome, Safari/WebKit, Firefox

## Installation

### 1. Install Dependencies

```bash
pip install playwright
playwright install chromium  # or: playwright install webkit
```

### 2. Install the Skill

Copy this directory to your Claude Code skills folder:

```bash
mkdir -p ~/.claude/skills
cp -r notebooklm ~/.claude/skills/
```

### 3. First-time Login

Run the login command to authenticate with your Google account:

```bash
python ~/.claude/skills/notebooklm/scripts/notebooklm.py login
```

This will open a browser window. Log in with your Google account, and the session will be saved.

## Usage

### CLI Commands

```bash
# List all notebooks
python ~/.claude/skills/notebooklm/scripts/notebooklm.py list

# List sources in a notebook
python ~/.claude/skills/notebooklm/scripts/notebooklm.py sources --notebook "Notebook Name"

# Smart chat (recommended)
python ~/.claude/skills/notebooklm/scripts/notebooklm.py smart-chat \
    --notebook "Notebook Name" \
    --question "Your question here"

# Smart chat and save response as note
python ~/.claude/skills/notebooklm/scripts/notebooklm.py smart-chat \
    --notebook "Notebook Name" \
    --question "Your question" \
    --save-note

# Search for new sources
python ~/.claude/skills/notebooklm/scripts/notebooklm.py search-sources \
    --notebook "Notebook Name" \
    --query "search terms" \
    --mode fast  # or: deep
    --source-type web  # or: drive, youtube, link

# Clear search results
python ~/.claude/skills/notebooklm/scripts/notebooklm.py clear-search \
    --notebook "Notebook Name"

# Detect search state
python ~/.claude/skills/notebooklm/scripts/notebooklm.py detect-search-state \
    --notebook "Notebook Name"

# Generate podcast audio
python ~/.claude/skills/notebooklm/scripts/notebooklm.py audio \
    --notebook "Notebook Name" \
    --output "/path/to/output.mp3"
```

### Browser Options

```bash
# Use isolated Chrome profile (default, doesn't affect your browser)
python ~/.claude/skills/notebooklm/scripts/notebooklm.py list

# Use your default Chrome profile (requires closing other Chrome windows)
python ~/.claude/skills/notebooklm/scripts/notebooklm.py list --user-profile

# Use WebKit (cross-platform, no conflicts)
python ~/.claude/skills/notebooklm/scripts/notebooklm.py list --browser webkit

# Headless mode (no visible browser)
python ~/.claude/skills/notebooklm/scripts/notebooklm.py list --headless
```

### Python API

```python
import sys
sys.path.insert(0, "~/.claude/skills/notebooklm/scripts")
from notebooklm import NotebookLMAutomation

nlm = NotebookLMAutomation(headless=False)
nlm.start()

# List notebooks
notebooks = nlm.list_notebooks()

# Smart chat
response = nlm.smart_chat("Notebook Name", "Your question")

# Search sources
results = nlm.search_sources("Notebook Name", "query", mode="fast")

# Clear search results
nlm.clear_temp_sources()

# Detect search state
state = nlm.detect_search_state()  # READY / PENDING_RESULTS / UNKNOWN

nlm.close()
```

## Search State Machine

NotebookLM requires handling search results before new searches:

```
READY (search box available)
    ↓ execute search
PENDING_RESULTS (results waiting)
    ↓ import or delete results
READY (back to initial state)
```

The `search-sources` command automatically clears pending results before searching.

## NotebookLM UI Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      NotebookLM Interface                    │
├─────────────────┬─────────────────────┬─────────────────────┤
│   SOURCE Panel  │    Chat Panel       │   STUDIO Panel      │
│    (left)       │     (center)        │     (right)         │
├─────────────────┼─────────────────────┼─────────────────────┤
│ • Source types  │ • Chat with sources │ • Save notes        │
│ • Research mode │ • View history      │ • Generate audio    │
│ • Search sources│ • Save as note      │ • Export content    │
│ • Import/remove │                     │                     │
└─────────────────┴─────────────────────┴─────────────────────┘
```

## File Structure

```
~/.claude/skills/notebooklm/
├── README.md           # This file
├── SKILL.md            # Claude Code skill protocol
├── scripts/
│   └── notebooklm.py   # Main automation script
├── chrome_profile/     # Isolated Chrome profile (gitignored)
├── webkit_profile/     # WebKit profile (gitignored)
└── .gitignore
```

## Requirements

- Python 3.8+
- Playwright
- Google account with NotebookLM access

## License

MIT License

## Contributing

Issues and PRs welcome!
