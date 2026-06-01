#!/bin/bash
# Pre-check script for code review
# 运行预检查：lint、格式检查、静态分析

set -e

FILE_PATH="${1:-.}"
echo "🔍 Running pre-check for: $FILE_PATH"

# 1. Python lint
if command -v flake8 &> /dev/null; then
    echo "  → Running flake8..."
    flake8 "$FILE_PATH" --max-line-length=100 || true
fi

# 2. Python format check
if command -v black &> /dev/null; then
    echo "  → Checking black format..."
    black --check "$FILE_PATH" || true
fi

# 3. Security scan
if command -v bandit &> /dev/null; then
    echo "  → Running bandit security scan..."
    bandit -r "$FILE_PATH" -f txt || true
fi

# 4. JavaScript lint (if applicable)
if command -v eslint &> /dev/null && [ -f "package.json" ]; then
    echo "  → Running eslint..."
    npx eslint "$FILE_PATH" || true
fi

echo "✅ Pre-check complete"
