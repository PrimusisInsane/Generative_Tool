# app/scripts/test_llm.py
import asyncio
from app.services.media_fetch import fetch_media_data
from app.services.generations import get_cached_or_generate_summary
from app.services.storage import save_summary
from app.db import async_session

async def main():
    title, media_type = "Inception", "movie"
    spoiler_level, length = "full", "long"

    source_data = await fetch_media_data(title, media_type)
    if source_data is None:
        print("No data found.")
        return

    validated, was_cached = await get_cached_or_generate_summary(
        title, media_type, spoiler_level, length, source_data
    )
    print(f"--- Validated (was_cached={was_cached}) ---")
    print(validated)

    async with async_session() as session:
        record = await save_summary(session, spoiler_level, length, validated)
    print("\n--- Saved to Postgres ---")
    print("id:", record.id)

if __name__ == "__main__":
    asyncio.run(main())