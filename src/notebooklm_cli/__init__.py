"""
NotebookLM CLI - Command line tool for automating Google NotebookLM

Features:
- Notebook management (list, create, delete)
- Source management (list, upload, search, import)
- Smart chat with notebooks
- Audio/podcast generation
- Cross-platform browser support
"""

__version__ = "1.0.0"
__author__ = "Superionichuan"

from .cli import NotebookLMAutomation

__all__ = ["NotebookLMAutomation", "__version__"]
