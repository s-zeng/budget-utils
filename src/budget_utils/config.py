from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CsvOutput(BaseModel):
    csv_output: Path = Field(alias="csv_output")

    model_config = {"populate_by_name": True}


class VisualOutput(BaseModel):
    visual_output: Path = Field(alias="visual_output")

    model_config = {"populate_by_name": True}


OutputFormat = Literal["polars_print", "csv_print"] | CsvOutput | VisualOutput


class Config(BaseModel):
    budget_name: str = Field(alias="budgetName")
    personal_access_token: str = Field(alias="personalAccessToken")
    category_group_watch_list: dict[str, str] = Field(alias="categoryGroupWatchList")
    resolution_date: datetime.date | None = Field(default=None, alias="resolution_date")
    show_all_rows: bool = Field(default=False, alias="showAllRows")
    output_format: OutputFormat = Field(default="polars_print", alias="outputFormat")

    model_config = {"populate_by_name": True}


def load_config(path: Path) -> Config:
    return Config.model_validate_json(path.read_text())
