BU_PERMISSION_MAP: dict[str, str] = {
    "delivery": "Recruitment - Delivery",
    "met":      "Recruitment - MWFL (MET)",
    "see":      "Recruitment - MWFL (SEE)",
    "security": "Recruitment - Security",
}

BU_GROUP_MAP: dict[str, list[str]] = {
    "delivery": [BU_PERMISSION_MAP["delivery"]],
    "met":      [BU_PERMISSION_MAP["met"]],
    "see":      [BU_PERMISSION_MAP["see"]],
    "security": [BU_PERMISSION_MAP["security"]],
    "mwfl":     [BU_PERMISSION_MAP["met"], BU_PERMISSION_MAP["see"]],
}

