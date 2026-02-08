# Agent Guidelines for ePublic Library

## Code and Documentation Standards

### No Personal Paths
- **Never use absolute paths** that contain personal machine information (usernames, computer names, local directory structures)
- **Bad**: `/Users/chrisford/Codigo/epublic-library`, `/Users/yourname/Documents/books`
- **Good**: `/path/to/epublic-library`, `~/Documents/books`
- **Best**: Relative paths using `os.path.join(os.path.dirname(__file__), ...)`

### Path References in Documentation
- Use placeholder paths like `/path/to/project-name` for generic instructions
- Use tilde expansion (`~`) for home directory references
- Use environment variables when appropriate
- Provide examples that users can adapt to their own systems

### Configuration Files
- Never hardcode personal paths in `pyproject.toml`, config files, or environment setup scripts
- Use environment variables or configuration arguments instead
- Document how users should customize paths for their own setup

### Before Committing
- Search for any hardcoded absolute paths containing usernames or machine names
- Verify all documentation examples use generic/placeholder paths
- Test that instructions work with generic path placeholders

## Example: Correct Path Handling

### Bad
```python
sys.path.insert(0, '/Users/chris/kindle-mcp/src')
```

### Good
```python
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
```

### Bad Documentation
```bash
cd /Users/yourname/projects/epublic-library
pip install -e .
```

### Good Documentation
```bash
cd /path/to/epublic-library
pip install -e .
```

## Cleanup Process

If personal paths are discovered:
1. Remove all hardcoded paths from source code
2. Update all documentation to use generic placeholders
3. Amend commits containing personal paths
4. Run `git reflog expire --expire=now --all && git gc --prune=now` to permanently remove old commits

## Verification Helpers

### Direct Invoke (Measure Metadata Cache)
Run from the repo root to compare first vs second load times:
```bash
cd /path/to/epublic-library
./venv/bin/python3 - <<'PY'
import time
from books import get_books

def run(label):
    start = time.perf_counter()
    books = get_books()
    elapsed = time.perf_counter() - start
    print(f"{label}: {len(books)} books in {elapsed:.2f}s")

run("first")
run("second")
PY
```

### Tail Logs (After Claude Desktop Test)
Use the standard Claude Desktop log location:
```bash
tail -n 200 ~/Library/Logs/Claude/mcp-server-epublic.log
```
