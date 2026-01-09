#!/usr/bin/env python3
"""Quick test of book parsing."""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from books import get_books
from search import search_metadata, search_topic

# Load books
print("Loading books...")
books = get_books()

print(f"\nFound {len(books)} books:")
for title, book in books.items():
    print(f"  - {title} by {book.author}")

# Test searches
if books:
    print("\n--- Testing search_metadata ---")
    results = search_metadata("Continuous", books)
    for result in results:
        print(f"Found: {result['title']} by {result['author']}")
    
    print("\n--- Testing search_topic ---")
    results = search_topic("effective", books, limit=5)
    for result in results[:3]:
        print(f"Book: {result['book']}")
        print(f"Quote: {result['quote'][:200]}...")
        print()
