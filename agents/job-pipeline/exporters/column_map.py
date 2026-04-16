"""Google Sheet column definitions."""

# Column headers in order (must match sheets_exporter.py logic)
HEADERS = [
    "Job Title",
    "Company",
    "Date Posted",
    "Salary",
    "Location",
    "Remote?",
    "Company Size (employees)",
    "Apply URL",
    "Job Board Source",
    "Status",
    "Flags",
    "Hiring Manager Name",
    "Hiring Manager Title",
    "LinkedIn URL",
    "Email",
    "Email Confidence",
    "Last Updated",
]

# Column letters (A=0, B=1, ...) for gspread col_values()
COL_IDX = {h: i for i, h in enumerate(HEADERS)}

# The "key" column used for deduplication — Apply URL is unique per posting
DEDUP_COL = "Apply URL"

# Columns that trigger conditional formatting (flag warnings)
FLAG_LOW_EMAIL_CONFIDENCE = "Email Confidence"
FLAG_STALE_POSTING = "Date Posted"
