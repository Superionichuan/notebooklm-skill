# NotebookLM CLI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Command-line tool for automating Google NotebookLM using **Chrome DevTools Protocol (CDP)**. Search sources, chat with notebooks, generate podcasts - all through CLI or Python API.

## Highlights

- **CDP Architecture** - Connects to existing Chrome via DevTools Protocol, no profile conflicts
- **Text Stability Detection** - Ensures complete responses (waits for text to stabilize before returning)
- **Multi-window Safe** - Multiple CLI instances can run simultaneously
- **Persistent Login** - Login once, stay logged in across sessions
- **Cross-platform** - macOS, Linux, Windows support

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CDP Architecture                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   nlm-cdp.sh / nlm wrapper                                       │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Chrome CDP Server (port 9222/9333)                      │   │
│   │  - Persistent browser instance                           │   │
│   │  - Shared across all nlm calls                           │   │
│   │  - Login state preserved                                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  notebooklm_cli (Playwright)                             │   │
│   │  - Connects via --cdp-url                                │   │
│   │  - No browser launch overhead                            │   │
│   │  - Text stability detection for complete responses       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Installation

### Step 1: Clone & Install

```bash
git clone https://github.com/Superionichuan/notebooklm-skill.git
cd notebooklm-skill

# Install package
pip install -e .

# Install Playwright browsers
playwright install chromium
```

### Step 2: Setup CDP Wrapper

**macOS:**
```bash
# Copy the CDP wrapper script
cp nlm-cdp.sh ~/.local/bin/nlm-cdp
chmod +x ~/.local/bin/nlm-cdp

# Or use directly
./nlm-cdp.sh --headless list
```

**Linux (with display):**
```bash
# Create wrapper script
cat > ~/bin/nlm << 'EOF'
#!/bin/bash
CDP_PORT=9222
CDP_URL="http://127.0.0.1:$CDP_PORT"
REAL_NLM="$(which nlm.real 2>/dev/null || which nlm)"
CHROME_PROFILE="$HOME/.claude/skills/notebooklm/chrome_profile"

# Start Chrome CDP if not running
if ! curl -s "$CDP_URL/json/version" > /dev/null 2>&1; then
    echo "Starting Chrome CDP..."
    DISPLAY=:0 nohup google-chrome \
        --remote-debugging-port=$CDP_PORT \
        --user-data-dir="$CHROME_PROFILE" \
        --no-first-run https://notebooklm.google.com &
    sleep 3
fi

exec $REAL_NLM --cdp-url "$CDP_URL" --no-auto-instance "$@"
EOF
chmod +x ~/bin/nlm
```

### Step 3: First-time Login

```bash
# This opens browser - login with Google account
nlm login

# Or with CDP wrapper
./nlm-cdp.sh login
```

---

## Quick Start

```bash
# List notebooks
nlm --headless list

# Chat with notebook (with text stability detection)
nlm --headless smart-chat \
    --notebook "My Research" \
    --question "Summarize the key findings"

# Search for sources
nlm --headless search-sources \
    --notebook "My Research" \
    --query "machine learning papers"

# Generate podcast
nlm --headless audio --notebook "My Research" --output podcast.mp3
```

---

## Text Stability Detection (v2.0)

The `smart-chat` command now uses **text stability detection** to ensure complete responses:

```
Response Detection Flow:
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: Wait for generation start (up to 60s)                  │
│   └── Detects "Stop generating" button appearing                │
├─────────────────────────────────────────────────────────────────┤
│ Phase 2: Wait for completion (up to max_wait, default 480s)     │
│   └── Text stable for 5 consecutive seconds = complete          │
├─────────────────────────────────────────────────────────────────┤
│ Phase 3: Final verification (5s)                                │
│   └── Confirms text is no longer changing                       │
└─────────────────────────────────────────────────────────────────┘
```

### Timeout Configuration

```bash
# Default: 8 minutes max wait
nlm --headless smart-chat --notebook "..." --question "..."

# Extended: 10 minutes for complex questions
nlm --headless smart-chat --notebook "..." --question "..." --max-wait 600
```

**Important for Claude Code users:** Set Bash timeout to at least 600 seconds (10 minutes):
```
Bash timeout: 600000 (10 minutes recommended)
```

---

## All Commands

### Notebook Management

| Command | Description |
|---------|-------------|
| `nlm list` | List all notebooks |
| `nlm create --name "Name"` | Create new notebook |
| `nlm delete --notebook "Name"` | Delete notebook |

### Source Management

| Command | Description |
|---------|-------------|
| `nlm sources --notebook "Name"` | List sources in notebook |
| `nlm upload --file path --notebook "Name"` | Upload document |
| `nlm delete-source --notebook "Name" --source "Name"` | Delete source |

### Search & Import

| Command | Description |
|---------|-------------|
| `nlm search-sources --notebook "..." --query "..."` | Search web |
| `nlm search-sources ... --mode deep` | Deep research |
| `nlm search-sources ... --source-type drive` | Search Drive |
| `nlm import-result --notebook "..." --title "..."` | Import result |
| `nlm clear-search --notebook "..."` | Clear results |

### Chat & Notes

| Command | Description |
|---------|-------------|
| `nlm smart-chat --notebook "..." --question "..."` | Chat (recommended) |
| `nlm smart-chat ... --save-note` | Chat + save as note |
| `nlm smart-chat ... --max-wait 600` | Extended timeout |
| `nlm save-note --notebook "..." --content "..."` | Save note |

### Audio

| Command | Description |
|---------|-------------|
| `nlm audio --notebook "Name"` | Generate podcast |
| `nlm audio ... --output file.mp3` | Save to file |

---

## Global Options

```bash
nlm [OPTIONS] COMMAND [ARGS]

Options:
  --headless              Run without visible browser
  --cdp-url URL           Connect to Chrome CDP (e.g., http://127.0.0.1:9222)
  --no-auto-instance      Don't auto-start browser instance
  --browser TYPE          Browser: chrome (default), webkit, firefox
  --timeout SECONDS       Global timeout for page operations
  -h, --help              Show help
```

---

## Python API

```python
from notebooklm_cli import NotebookLMAutomation

# Create instance (CDP mode recommended)
nlm = NotebookLMAutomation(headless=True)
nlm.start()

# List notebooks
notebooks = nlm.list_notebooks()

# Smart chat with text stability detection
response = nlm.smart_chat(
    notebook_name="My Research",
    question="What are the key findings?",
    max_wait=480  # 8 minutes
)
print(f"Response length: {len(response)} chars")

# Search sources
results = nlm.search_sources(
    notebook_name="My Research",
    query="machine learning",
    mode="fast",  # or "deep"
    source_type="web"  # or "drive", "youtube", "link"
)

# Check search state
state = nlm.detect_search_state()  # READY / PENDING_RESULTS

# Clear search results
nlm.clear_temp_sources()

# Close
nlm.close()
```

---

## File Structure

```
notebooklm-skill/
├── README.md               # This file
├── SKILL.md                # Claude Code skill protocol
├── QUICK_START.md          # Quick start guide
├── nlm-cdp.sh              # macOS CDP wrapper
├── pyproject.toml          # Package config
├── src/
│   └── notebooklm_cli/
│       ├── __init__.py
│       └── cli.py          # Main CLI (with text stability detection)
├── scripts/
│   └── notebooklm.py       # Standalone script
└── chrome_profile/         # Isolated Chrome profile (gitignored)
```

---

## Troubleshooting

### "Cannot connect to Chrome CDP"

Start Chrome with CDP enabled:
```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9333 \
    --user-data-dir="$HOME/.claude/skills/notebooklm/chrome_profile" \
    --no-first-run https://notebooklm.google.com

# Linux
google-chrome --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.claude/skills/notebooklm/chrome_profile" \
    --no-first-run https://notebooklm.google.com
```

### "Profile lock" error

```bash
rm -f ~/.claude/skills/notebooklm/chrome_profile/Singleton*
```

### Response truncated

Increase timeout:
```bash
nlm --headless smart-chat --notebook "..." --question "..." --max-wait 600
```

### "Not logged in"

```bash
nlm login  # Opens browser for Google login
```

---

## Changelog

### v2.0.0 (2025-01-18)
- **CDP Architecture** - Connect to existing Chrome via DevTools Protocol
- **Text Stability Detection** - Wait for response text to stabilize before returning
- **`--max-wait` parameter** - Configurable wait time (default 480s / 8 minutes)
- **`_get_latest_response_text()`** - New helper for reliable response extraction
- **Multi-window safe** - Multiple CLI instances work simultaneously
- **Enhanced timeout docs** - Clear timeout hierarchy for Claude Code integration

### v1.x
- Initial release with Playwright automation
- Source search workflow
- Audio generation

---

## Requirements

- Python 3.8+
- Playwright
- Google Chrome (for CDP mode)
- Google account with NotebookLM access

---

## License

MIT License

---

## Links

- [GitHub Repository](https://github.com/Superionichuan/notebooklm-skill)
- [Google NotebookLM](https://notebooklm.google.com/)
