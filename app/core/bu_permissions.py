BU_PERMISSION_MAP: dict[str, str] = {
    "delivery": "Recruitment - Delivery",
    "met":      "Recruitment - MWFL (MET)",
    "see":      "Recruitment - MWFL (SEE)",
    "security": "Recruitment - Security",
}

BU_GROUP_MAP: dict[str, list[str]] = {
    "MWFL":     ["Recruitment - MWFL (MET)", "Recruitment - MWFL (SEE)"],
    "Delivery": ["Recruitment - Delivery"],
    "Security": ["Recruitment - Security"],
}