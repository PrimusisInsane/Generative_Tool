import asyncio
from app.services.media_fetch import fetch_media_data

async def main():
    movie = await fetch_media_data("Inception", "movie")
    print("--- Movie ---")
    print(movie)

    book = await fetch_media_data("Dune", "book")
    print("\n--- Book ---")
    print(book)

if __name__ == "__main__":
    asyncio.run(main())