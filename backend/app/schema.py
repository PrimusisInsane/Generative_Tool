from pydantic import BaseModel
from typing import Literal

class SummaryResponse(BaseModel):
    title: str
    media_type: Literal["book", "movie"]
    genre: list[str]
    themes: list[str]
    summary: str
    confidence: Literal["high", "medium", "low"]