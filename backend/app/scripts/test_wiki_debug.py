# app/scripts/test_wiki_debug.py
import asyncio
from app.services.wiki_fetch import wiki

async def main():
    for query in ["Dune (film)", "Dune (2021 film)", "Dune"]:
        page = wiki.page(query)
        exists = await page.exists()
        print(f"'{query}' exists: {exists}")
        if exists:
            sections = await page.sections
            titles = [s.title for s in sections]
            print(f"  Section titles: {titles}")

if __name__ == "__main__":
    asyncio.run(main())