# app/scripts/test_wiki.py
import asyncio
from app.services.wiki_fetch import fetch_wikipedia_plot

async def main():
    plot = await fetch_wikipedia_plot("Dune", "movie")
    print("--- Dune (movie) plot ---")
    print(plot[:300] if plot else "None found")
    print(f"\nLength: {len(plot.split()) if plot else 0} words")

if __name__ == "__main__":
    asyncio.run(main())