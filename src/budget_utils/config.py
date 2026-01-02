from __future__ import annotations

import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    budget_name: str = Field(alias="budgetName")
    personal_access_token: str = Field(alias="personalAccessToken")
    category_group_watch_list: list[str] = Field(alias="categoryGroupWatchList")
    resolution_date: datetime.date | None = Field(default=None, alias="resolution_date")
    show_all_rows: bool = Field(default=False, alias="showAllRows")

    model_config = {"populate_by_name": True}


def load_config(path: Path) -> Config:
    return Config.model_validate_json(path.read_text())
