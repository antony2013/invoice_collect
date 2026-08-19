from __future__ import annotations

from typing import Annotated

from fastapi import Query

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]
