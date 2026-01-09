# Setting Up ePublic Library with Claude Desktop

## Step 1: Install Python Dependencies

The MCP server requires a Python virtual environment with specific packages.

```bash
cd /path/to/epublic-library
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Step 2: Configure Claude Desktop

Edit the Claude Desktop config file:

```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add this to the `mcpServers` section:

```json
{
  "mcpServers": {
    "epublic": {
      "command": "/path/to/epublic-library/venv/bin/python3",
      "args": ["/path/to/epublic-library/src/main.py"]
    }
  }
}
```

**Note**: If `claude_desktop_config.json` doesn't exist, create it with:

```json
{
  "mcpServers": {
    "epublic": {
      "command": "/path/to/epublic-library/venv/bin/python3",
      "args": ["/path/to/epublic-library/src/main.py"]
    }
  }
}
```

## Step 3: Restart Claude Desktop

After updating the config, fully restart Claude Desktop for the changes to take effect.

## Step 4: Use in Claude

Once configured, you can use these tools in Claude:

### `search_books`
```
search_books(query="Continuous Deployment")
```
Returns matching books with metadata (author, publication year, chapters).

### `find_topic`
```
find_topic(topic="effective teams", limit=10)
```
Returns passages mentioning the topic with full attribution (book, author, section, quote).

## Troubleshooting

**Tools not appearing?**
- Check that the Python path is correct in the config
- Verify the venv was created successfully
- Restart Claude Desktop completely

**Book parsing errors?**
- Only EPUB files are currently supported
- The server looks in `~/Library/Application Support/Amazon/Kindle/` and `~/Sync/`
- Add your own book paths by editing `src/books.py`

## Adding Your Kindle Books

Your Kindle books should be in:
```
~/Library/Application Support/Amazon/Kindle/
```

Or for testing, place EPUB files in:
```
~/Sync/
```

The server scans these directories on startup and caches all books in memory.
