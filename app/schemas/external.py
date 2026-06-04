from dataclasses import dataclass

@dataclass
class ExternalCaller:
    employee_id: str
    bu_group:    str
    allowed_bus: list[str]