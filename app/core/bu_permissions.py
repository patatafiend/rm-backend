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

APPRAISALS_BU_GROUP_MAP: dict[str, list[str]] = {
    "delivery": [],
    "met":      ["MWFL"],
    "see":      ["MWFL"],
    "security": ["Security"],
    "mwfl":     ["MWFL"],
}

APPRAISALS_CATEGORY_MAP: dict[str, list[str]] = {
    "staff":     ["STAFF"],
    "non_staff": ["GUARD", "MANPOWER"],
}

APPRAISALS_CATEGORY_ALIASES: dict[str, str] = {
    "guard":     "non_staff",
    "manpower":  "non_staff",
    "staff":     "staff",
}

