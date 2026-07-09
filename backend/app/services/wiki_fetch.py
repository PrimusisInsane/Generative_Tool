import wikipediaapi

PLOT_SECTION_NAMES = ["Plot", "Plot summary", "Synopsis", "Story"]

wiki = wikipediaapi.AsyncWikipedia(
    user_agent="MediaSummarizerApp/1.0 (personal learning project)",
    language="en",
)


def _find_plot_section(sections) -> str | None:
    for section in sections:
        if section.title in PLOT_SECTION_NAMES:
            return section.text
    return None


async def fetch_wikipedia_plot(title: str, media_type: str) -> str | None:
    """
    Searches Wikipedia for the title (biased toward film/novel pages),
    then checks each search result in ranked order until one has an
    actual plot section. Returns None if nothing usable is found.
    """
    hint = "film" if media_type == "movie" else "novel"

    results = await wiki.search(f"{title} {hint}", limit=5)

    for page_title, page in results.pages.items():
        if not await page.exists():
            continue

        sections = await page.sections
        plot = _find_plot_section(sections)

        if plot:
            return plot.strip()

    return None