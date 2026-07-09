import json
from ariadne import QueryType, MutationType, make_executable_schema, gql
from sqlalchemy import select
from app.services.media_fetch import fetch_media_data
from app.services.generations import get_cached_or_generate_summary
from app.services.storage import save_summary
from app.db import async_session
from app.models import Summary

type_defs = gql("""
    type Query {
        hello: String!
        summaries: [SummaryRecord!]!
    }

    type Mutation {
        generateSummary(
            title: String!
            mediaType: String!
            spoilerLevel: String!
            length: String!
        ): SummaryResult
    }

    type SummaryResult {
        id: Int!
        title: String!
        mediaType: String!
        genre: [String!]!
        themes: [String!]!
        summary: String!
        confidence: String!
        createdAt: String!
    }

    type SummaryRecord {
        id: Int!
        title: String!
        mediaType: String!
        spoilerLevel: String!
        length: String!
        generatedOutput: String!
        createdAt: String!
    }
""")

query = QueryType()
mutation = MutationType()


@query.field("hello")
def resolve_hello(_, info):
    return "GraphQL is wired up"


@query.field("summaries")
async def resolve_summaries(_, info):
    async with async_session() as session:
        result = await session.execute(
            select(Summary).order_by(Summary.created_at.desc())
        )
        records = result.scalars().all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "mediaType": r.media_type,
            "spoilerLevel": r.spoiler_level,
            "length": r.length,
            "generatedOutput": r.generated_output,
            "createdAt": r.created_at.isoformat(),
        }
        for r in records
    ]


@mutation.field("generateSummary")
async def resolve_generate_summary(_, info, title: str, mediaType: str, spoilerLevel: str, length: str):
    source_data = await fetch_media_data(title, mediaType)
    print("--- DEBUG: fetched source_data ---")
    print(source_data)

    if source_data is None:
        return None  # no match found — frontend should handle null gracefully

    validated, was_cached = await get_cached_or_generate_summary(
        title, mediaType, spoilerLevel, length, source_data
    )

    async with async_session() as session:
        record = await save_summary(session, spoilerLevel, length, validated)

    return {
        "id": record.id,
        "title": validated.title,
        "mediaType": validated.media_type,
        "genre": validated.genre,
        "themes": validated.themes,
        "summary": validated.summary,
        "confidence": validated.confidence,
        "createdAt": record.created_at.isoformat(),
    }


schema = make_executable_schema(type_defs, query, mutation)