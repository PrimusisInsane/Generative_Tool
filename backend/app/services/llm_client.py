import re
from google import genai
from app.config import settings
from app.services.prompts import SUMMARY_SYSTEM_PROMPT, build_summary_user_prompt

client = genai.Client(api_key=settings.gemini_api_key)


def _strip_markdown_fences(text: str) -> str:
    """
    Gemini sometimes wraps JSON output in ```json ... ``` fences despite
    instructions not to. This strips them so downstream json.loads() works.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def call_llm(source_data: dict, spoiler_level: str, length: str) -> str:
    """
    Calls Gemini with real fetched media data (from TMDB/Google Books)
    and the requested spoiler level / length, asking it to rewrite the
    data into a structured summary.
    """
    user_prompt = build_summary_user_prompt(source_data, spoiler_level, length)
    full_prompt = f"{SUMMARY_SYSTEM_PROMPT}\n\n{user_prompt}"

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=full_prompt,
    )

    return _strip_markdown_fences(response.text)