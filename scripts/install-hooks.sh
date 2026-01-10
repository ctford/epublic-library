#!/bin/bash
# Install git pre-commit hooks for the project

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"

echo "Installing pre-commit hook..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Create the pre-commit hook script
cat > "$PRE_COMMIT_HOOK" << 'EOF'
#!/bin/bash
# Pre-commit hook: Run tests before allowing commit

# Get the repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Running tests..."
"$REPO_ROOT/venv/bin/python3" -m pytest tests/ -v

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed. Commit aborted."
    echo ""
    echo "To run tests manually: pytest tests/ -v"
    echo "To skip this hook: git commit --no-verify"
    exit 1
fi

echo ""
echo "✓ All tests passed"
exit 0
EOF

# Make the hook executable
chmod +x "$PRE_COMMIT_HOOK"

echo "✓ Pre-commit hook installed at $PRE_COMMIT_HOOK"
echo ""
echo "The hook will run: \$REPO_ROOT/venv/bin/python3 -m pytest tests/ -v"
echo "To bypass the hook, use: git commit --no-verify"
