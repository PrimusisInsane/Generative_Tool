from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Summary
from app.schema import SummaryResponse


async def save_summary(
    session: AsyncSession,
    spoiler_level: str,
    length: str,
    validated: SummaryResponse,
) -> Summary:
    record = Summary(
        title=validated.title,
        media_type=validated.media_type,
        spoiler_level=spoiler_level,
        length=length,
        generated_output=validated.model_dump_json(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record