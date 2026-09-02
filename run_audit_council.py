#!/usr/bin/env python3
"""
Launcher script for Financial Audit Council (Standalone Local Runner).

Usage:
  python3 run_audit_council.py --sample
  python3 run_audit_council.py --doc1 path/to/bs.txt --doc2 path/to/pl.txt --doc3 path/to/moa.txt
"""

import sys
from pathlib import Path

# Ensure Project_AccountingLegalChatbot is in sys.path
root_dir = Path(__file__).resolve().parent
pkg_dir = root_dir / "Project_AccountingLegalChatbot"
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from audit_council_local.cli import main

if __name__ == "__main__":
    main()
