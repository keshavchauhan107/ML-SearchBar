from pydantic import BaseModel
from typing import List, Optional

class ImpressionEvent(BaseModel):
    type: str
    query: str
    candidates: List[str]
    clicked: Optional[str] = None

class ClickEvent(BaseModel):
    type: str
    query: str
    candidate: str