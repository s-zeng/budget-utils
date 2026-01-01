from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    budget_name: str = Field(alias="budgetName")
    personal_access_token: str = Field(alias="personalAccessToken")
    category_group_watch_list: list[str] = Field(alias="categoryGroupWatchList")

    model_config = {"populate_by_name": True}


def load_config(path: Path) -> Config:
    return Config.model_validate_json(path.read_text())
