from typing import NewType

import polars as pl

Uuid = NewType("Uuid", str)
TransactionFrame = NewType("TransactionFrame", pl.LazyFrame)
CategoryFrame = NewType("CategoryFrame", pl.LazyFrame)
