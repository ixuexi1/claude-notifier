#!/bin/bash
# Claude Notifier — macOS/Linux one-liner installer
# Run: curl -fsSL https://.../install.sh | bash

set -e

echo ""
echo "  ✦ Claude Notifier v2.0.0"
echo "  Installing..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Install from https://python.org"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "  Installing package..."
pip install -e "$PROJECT_DIR" > /dev/null 2>&1

echo "  Enabling notifications..."
cn on

echo ""
echo "  ✓ Done! Run 'cn configure' to customize, or 'cn test' to verify."
echo "  Commands: cn on | cn off | cn test | cn status | cn sound | cn configure"
echo ""
