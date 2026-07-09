import httpx
from app.config import settings
from app.services.wiki_fetch import fetch_wikipedia_plot


TMDB_BASE_URL = "https://api.themoviedb.org/3"
GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"


async def fetch_movie_data(title: str) -> dict | None:
    headers = {"Authorization": f"Bearer {settings.tmdb_read_access_token}"}

    async with httpx.AsyncClient() as client:
        search_resp = await client.get(
            f"{TMDB_BASE_URL}/search/movie",
            headers=headers,
            params={"query": title},
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("results", [])

        if not results:
            return None

        top_match = results[0]
        movie_id = top_match["id"]

        detail_resp = await client.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}",
            headers=headers,
        )
        detail_resp.raise_for_status()
        details = detail_resp.json()

    return {
        "title": details.get("title"),
        "genres": [g["name"] for g in details.get("genres", [])],
        "overview": details.get("overview"),
        "release_date": details.get("release_date"),
        "vote_average": details.get("vote_average"),
        "vote_count": details.get("vote_count"),
    }


async def fetch_book_data(title: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_BOOKS_BASE_URL,
            params={
                "q": f"intitle:{title}",
                "key": settings.google_books_api_key,
                "maxResults": 10,  # widen further since exact matches get filtered
            },
        )
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return None

    def title_matches(item: dict) -> bool:
        item_title = item.get("volumeInfo", {}).get("title", "")
        return item_title.strip().lower() == title.strip().lower()

    # Only consider items whose title actually matches what was searched
    exact_matches = [item for item in items if title_matches(item)]

    if not exact_matches:
        # No exact title match at all — bail rather than return a wrong book
        return None

    # Among exact matches, prefer one with a real description
    best = next(
        (item for item in exact_matches if item.get("volumeInfo", {}).get("description")),
        exact_matches[0],
    )

    volume_info = best.get("volumeInfo", {})

    return {
        "title": volume_info.get("title"),
        "authors": volume_info.get("authors", []),
        "categories": volume_info.get("categories", []),
        "description": volume_info.get("description"),
        "published_date": volume_info.get("publishedDate"),
        "average_rating": volume_info.get("averageRating"),
    }

async def fetch_media_data(title: str, media_type: str) -> dict | None:
    """
    Dispatches to the correct metadata fetcher (TMDB or Google Books),
    then enriches the result with a full Wikipedia plot section if
    available. Returns None only if the metadata fetch itself fails.
    """
    if media_type == "movie":
        metadata = await fetch_movie_data(title)
    elif media_type == "book":
        metadata = await fetch_book_data(title)
    else:
        raise ValueError(f"Unknown media_type: {media_type}")

    if metadata is None:
        return None

    plot = await fetch_wikipedia_plot(title, media_type)
    metadata["full_plot"] = plot  # None if Wikipedia had nothing — that's fine

    return metadata


        