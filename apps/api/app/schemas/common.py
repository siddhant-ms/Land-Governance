from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.services.retrieval.types import SearchFilters


class FiltersIn(BaseModel):
    states: list[str] = Field(default_factory=list, max_length=30)
    districts: list[str] = Field(default_factory=list, max_length=30)
    date_from: date | None = None
    date_to: date | None = None
    source_types: list[str] = Field(default_factory=list, max_length=10)
    organizations: list[str] = Field(default_factory=list, max_length=30)
    topics: list[str] = Field(default_factory=list, max_length=30)
    document_types: list[str] = Field(default_factory=list, max_length=10)

    def to_filters(self) -> SearchFilters:
        return SearchFilters(**self.model_dump())


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    filters: FiltersIn = Field(default_factory=FiltersIn)
    top_k: int = Field(default=10, ge=1, le=30)


class AskIn(BaseModel):
    question: str = Field(min_length=5, max_length=600)
    filters: FiltersIn = Field(default_factory=FiltersIn)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
