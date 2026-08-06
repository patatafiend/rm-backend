from dataclasses import dataclass

@dataclass
class ExternalCaller:
    employee_id: str
    bu_group:    str
    allowed_bus: list[str]
    # None = unrestricted on this axis (category param wasn't supplied to
    # /authorize, or the token predates this feature). A list = restricted
    # to those ecategory values.
    allowed_categories: list[str] | None = None