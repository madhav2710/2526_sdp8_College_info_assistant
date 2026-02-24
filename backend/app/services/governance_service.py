from typing import Optional


def normalize_sort_order(sort_order: Optional[str], default: str = "desc") -> str:
    if not sort_order:
        return default
    value = sort_order.lower()
    return value if value in {"asc", "desc"} else default


def normalize_status_filter(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    return status.strip().lower().replace(" ", "_")


def normalize_search_term(search: Optional[str]) -> Optional[str]:
    if not search:
        return None
    value = search.strip()
    return value or None
