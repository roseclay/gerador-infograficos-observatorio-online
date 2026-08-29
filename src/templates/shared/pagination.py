from __future__ import annotations

from typing import Any


def paginate(metrics: list[Any], per_page: int) -> list[list[Any]]:
    if per_page < 1:
        raise ValueError("per_page precisa ser maior que zero")
    return [metrics[index:index + per_page] for index in range(0, len(metrics), per_page)]
