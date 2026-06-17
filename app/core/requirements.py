"""
Requirement definitions and mappings for employee onboarding.
Defines both universal requirements (all employees) and company-specific requirements.
"""

# Universal requirements that ALL employees must provide
UNIVERSAL_REQUIRED_REQS = [
    "CDI Affidavit",
    "Certificate, Birth",
    "Certificate, Employment",
    "Certificate, Training",
    "Clearance, Barangay",
    "Diploma, College",
    "Diploma, High School",
    "Job Description",
    "Medical, CBC",
    "Medical, Urinalysis",
    "Policy Acknowledgement Form",
    "TIN Number",
    "Transcript of Records",
]

# Company-specific requirements mapped by company name (hr_company field)
COMPANY_SPECIFIC_REQS: dict[str, list[str]] = {
    "E-MOBILE MATRIX LOGISTICS CORPORATION": [
        "Endorsement Letter (for Emobile Drivers)",
    ],
    # Add more companies and their specific requirements here
    # "COMPANY_NAME": ["Requirement 1", "Requirement 2"],
}
