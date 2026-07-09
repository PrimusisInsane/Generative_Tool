import asyncio
import json
from pydantic import ValidationError
from google.genai import errors as genai_errors
from redis.asyncio import Redis
from app.services.llm_client import call_llm
from app.schema import SummaryResponse
from app.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_validated_summary(
    source_data: dict, spoiler_level: str, length: str, max_retries: int = 2
) -> SummaryResponse:
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            raw = await call_llm(source_data, spoiler_level, length)
            parsed = json.loads(raw)
            return SummaryResponse.model_validate(parsed)
        except genai_errors.ServerError as e:
            print(f"Attempt {attempt + 1}: server error ({e}), retrying...")
            last_error = e
            await asyncio.sleep(2)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Attempt {attempt + 1}: validation failed ({e}), retrying...")
            last_error = e

    raise last_error


def _cache_key(title: str, media_type: str, spoiler_level: str, length: str) -> str:
    # normalize title casing so "Dune" and "dune" hit the same cache entry
    normalized_title = title.strip().lower()
    return f"summary:{media_type}:{normalized_title}:{spoiler_level}:{length}"


async def get_cached_or_generate_summary(
    title: str,
    media_type: str,
    spoiler_level: str,
    length: str,
    source_data: dict,
) -> tuple[SummaryResponse, bool]:
    """
    Checks Redis for a cached summary matching all four params first.
    Returns (validated_response, was_cached).
    """
    cache_key = _cache_key(title, media_type, spoiler_level, length)

    cached = await redis_client.get(cache_key)
    if cached:
        return SummaryResponse.model_validate(json.loads(cached)), True

    validated = await get_validated_summary(source_data, spoiler_level, length)
    await redis_client.set(cache_key, validated.model_dump_json(), ex=3600)
    return validated, False