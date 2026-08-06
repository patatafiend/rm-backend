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

# The appraisals (PAM) system sources bu_tagging from the newer two-feed
# employee data (the bu_grouping field), which only ever bundles employees
# into "Security" or "MWFL" — the granular delivery/met/see split above
# doesn't exist in that data. Keep the same 4 permission groups as query
# params, but point them at the bundled values where one exists.
# "delivery" has no bundled equivalent, so it resolves to an empty allow
# list (a valid group that just never matches any appraisal record).
APPRAISALS_BU_GROUP_MAP: dict[str, list[str]] = {
    "delivery": [],
    "met":      ["MWFL"],
    "see":      ["MWFL"],
    "security": ["Security"],
    "mwfl":     ["MWFL"],
}

