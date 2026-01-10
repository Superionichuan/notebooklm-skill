# NotebookLM CLI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Command-line tool for automating Google NotebookLM - search sources, chat with notebooks, generate podcasts, and more.

## Features

- **Notebook Management** - List, create, delete notebooks
- **Source Management** - List, upload, search & import web sources
- **Smart Chat** - Chat with notebooks, auto-save responses as notes
- **Audio Generation** - Generate podcast audio from notebooks
- **State Management** - Automatic handling of search state machine
- **Cross-platform** - Supports Chrome, WebKit, Firefox

---

## Installation

### Method 1: pip install (Recommended)

```bash
# Clone the repository
git clone https://github.com/Superionichuan/notebooklm-skill.git
cd notebooklm-skill

# Install the package
pip install -e .

# Install browser (first time only)
playwright install chromium
```

### Method 2: Direct use

```bash
# Clone the repository
git clone https://github.com/Superionichuan/notebooklm-skill.git

# Install dependencies
pip install playwright
playwright install chromium

# Run directly
python notebooklm-skill/src/notebooklm_cli/cli.py --help
```

---

## Quick Start

### 1. First-time Login

```bash
nlm login
```

This opens a browser window. Log in with your Google account - the session will be saved.

### 2. List Your Notebooks

```bash
nlm list
```

### 3. Chat with a Notebook

```bash
nlm smart-chat --notebook "My Notebook" --question "What is the main topic?"
```

### 4. Search for New Sources

```bash
nlm search-sources --notebook "My Notebook" --query "machine learning"
```

---

## All Commands

### Notebook Management

| Command | Description | Example |
|---------|-------------|---------|
| `nlm list` | List all notebooks | `nlm list` |
| `nlm create --name "Name"` | Create new notebook | `nlm create --name "Research"` |
| `nlm delete --notebook "Name"` | Delete a notebook | `nlm delete --notebook "Old Notes"` |

### Source Management

| Command | Description | Example |
|---------|-------------|---------|
| `nlm sources --notebook "Name"` | List all sources | `nlm sources --notebook "Research"` |
| `nlm upload --file path --notebook "Name"` | Upload document | `nlm upload --file paper.pdf --notebook "Research"` |
| `nlm delete-source --notebook "Name" --source "Source"` | Delete a source | `nlm delete-source --notebook "Research" --source "paper.pdf"` |

### Search & Import Sources

| Command | Description | Example |
|---------|-------------|---------|
| `nlm search-sources --notebook "Name" --query "term"` | Search web sources | `nlm search-sources --notebook "Research" --query "AI"` |
| `nlm search-sources ... --mode deep` | Deep research mode | `nlm search-sources --notebook "Research" --query "AI" --mode deep` |
| `nlm search-sources ... --source-type drive` | Search Google Drive | `nlm search-sources --notebook "Research" --query "notes" --source-type drive` |
| `nlm import-result --notebook "Name" --title "Title"` | Import a result | `nlm import-result --notebook "Research" --title "AI Paper"` |
| `nlm clear-search --notebook "Name"` | Clear search results | `nlm clear-search --notebook "Research"` |
| `nlm detect-search-state --notebook "Name"` | Check search state | `nlm detect-search-state --notebook "Research"` |

### Chat & Notes

| Command | Description | Example |
|---------|-------------|---------|
| `nlm smart-chat --notebook "Name" --question "Q"` | Chat with notebook | `nlm smart-chat --notebook "Research" --question "Summarize"` |
| `nlm smart-chat ... --save-note` | Chat and save as note | `nlm smart-chat --notebook "Research" --question "Summarize" --save-note` |
| `nlm save-note --notebook "Name" --content "Text"` | Save a note | `nlm save-note --notebook "Research" --content "Important point"` |

### Audio Generation

| Command | Description | Example |
|---------|-------------|---------|
| `nlm audio --notebook "Name"` | Generate podcast | `nlm audio --notebook "Research"` |
| `nlm audio --notebook "Name" --output file.mp3` | Save to file | `nlm audio --notebook "Research" --output podcast.mp3` |

### Utility

| Command | Description | Example |
|---------|-------------|---------|
| `nlm login` | Login to Google | `nlm login` |
| `nlm detect-mode --notebook "Name"` | Detect UI mode | `nlm detect-mode --notebook "Research"` |

---

## Global Options

```bash
nlm [command] [options]

Options:
  --headless          Run without visible browser
  --user-profile      Use your default Chrome profile (requires closing Chrome)
  --browser TYPE      Browser engine: chrome (default), webkit, firefox
  -h, --help          Show help message
```

### Browser Options

```bash
# Default: isolated Chrome profile (doesn't affect your browser)
nlm list

# Use WebKit (cross-platform, no Chrome conflicts)
nlm list --browser webkit

# Headless mode (no visible browser)
nlm list --headless

# Use your Chrome profile (need to close other Chrome windows)
nlm list --user-profile
```

---

## Search State Machine

NotebookLM requires handling search results before new searches:

```
┌─────────────────────────────────────────┐
│  READY                                   │
│  - Search box available                  │
│  - Can start new search                  │
└────────────────┬────────────────────────┘
                 │ execute search
                 ▼
┌─────────────────────────────────────────┐
│  PENDING_RESULTS                         │
│  - Results waiting                       │
│  - Must import or clear before new search│
└────────────────┬────────────────────────┘
                 │ import or clear
                 ▼
┌─────────────────────────────────────────┐
│  READY (back to initial state)           │
└─────────────────────────────────────────┘
```

**Note:** `search-sources` automatically clears pending results before searching.

---

## Python API

```python
from notebooklm_cli import NotebookLMAutomation

# Create instance
nlm = NotebookLMAutomation(headless=False)
nlm.start()

# List notebooks
notebooks = nlm.list_notebooks()
print(notebooks)

# Smart chat
response = nlm.smart_chat("My Notebook", "What is the main topic?")
print(response)

# Search sources
results = nlm.search_sources("My Notebook", "machine learning", mode="fast")
print(f"Found {len(results)} results")

# Clear search results
nlm.clear_temp_sources()

# Check search state
state = nlm.detect_search_state()  # READY / PENDING_RESULTS / UNKNOWN

# Close
nlm.close()
```

---

## NotebookLM UI Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      NotebookLM Interface                    │
├─────────────────┬─────────────────────┬─────────────────────┤
│   SOURCE Panel  │    Chat Panel       │   STUDIO Panel      │
│    (left)       │     (center)        │     (right)         │
├─────────────────┼─────────────────────┼─────────────────────┤
│ • Source types  │ • Chat with sources │ • Save notes        │
│   - Web         │ • View history      │ • Generate audio    │
│   - Drive       │ • Save as note      │ • Export content    │
│   - YouTube     │                     │                     │
│   - Link        │                     │                     │
│ • Research mode │                     │                     │
│   - Fast        │                     │                     │
│   - Deep        │                     │                     │
│ • Search box    │                     │                     │
│ • Import/remove │                     │                     │
└─────────────────┴─────────────────────┴─────────────────────┘
```

---

## File Structure

```
notebooklm-skill/
├── README.md              # This file
├── SKILL.md               # Claude Code skill protocol
├── pyproject.toml         # Package configuration
├── src/
│   └── notebooklm_cli/
│       ├── __init__.py    # Package init
│       └── cli.py         # Main CLI script
├── scripts/
│   └── notebooklm.py      # Standalone script (legacy)
└── .gitignore
```

---

## Requirements

- Python 3.8+
- Playwright
- Google account with NotebookLM access

---

## Troubleshooting

### "Browser not installed"

```bash
playwright install chromium
```

### "Profile in use" error

Close all Chrome windows, or use WebKit:

```bash
nlm list --browser webkit
```

### "Not logged in"

```bash
nlm login
```

### Search stuck / can't search

Clear pending results:

```bash
nlm clear-search --notebook "Your Notebook"
```

---

## License

MIT License

## Contributing

Issues and PRs welcome!

---

## Links

- [GitHub Repository](https://github.com/Superionichuan/notebooklm-skill)
- [Google NotebookLM](https://notebooklm.google.com/)
