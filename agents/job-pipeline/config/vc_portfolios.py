# Curated list of VC portfolio companies with their ATS slugs.
# These feed directly into the Greenhouse/Lever/Ashby scrapers.
#
# Format: {"ats": "greenhouse|lever|ashby", "slug": "<company-slug>"}
# Greenhouse URL: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
# Lever URL:      https://api.lever.co/v0/postings/{slug}?mode=json
# Ashby URL:      https://api.ashbyhq.com/posting-api/job-board/{slug}

A16Z_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "a16z"},
    {"ats": "greenhouse", "slug": "figma"},
    {"ats": "greenhouse", "slug": "ramp"},
    {"ats": "greenhouse", "slug": "brex"},
    {"ats": "greenhouse", "slug": "instacart"},
    {"ats": "greenhouse", "slug": "lyft"},        # moved from lever
    {"ats": "greenhouse", "slug": "robinhood"},
    {"ats": "greenhouse", "slug": "samsara"},
    {"ats": "greenhouse", "slug": "databricks"},
    {"ats": "greenhouse", "slug": "ziprecruiter"},
    {"ats": "greenhouse", "slug": "kajabi"},
    {"ats": "greenhouse", "slug": "lattice"},
    {"ats": "ashby", "slug": "notion"},           # moved from lever
    {"ats": "greenhouse", "slug": "benchling"},

    {"ats": "greenhouse", "slug": "chime"},
    {"ats": "greenhouse", "slug": "carta"},
]

SEQUOIA_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "stripe"},
    {"ats": "greenhouse", "slug": "airbnb"},      # moved from lever
    {"ats": "greenhouse", "slug": "dropbox"},
    {"ats": "greenhouse", "slug": "zoom"},
    {"ats": "lever", "slug": "whoop"},            # still on lever
    {"ats": "greenhouse", "slug": "nubank"},
    {"ats": "greenhouse", "slug": "snowflake"},
    {"ats": "greenhouse", "slug": "doordash"},
    {"ats": "greenhouse", "slug": "klarna"},
    {"ats": "greenhouse", "slug": "square"},
    {"ats": "greenhouse", "slug": "hubspot"},
    {"ats": "greenhouse", "slug": "pagerduty"},
    {"ats": "greenhouse", "slug": "servicenow"},
    {"ats": "greenhouse", "slug": "gusto"},       # moved from lever
    {"ats": "greenhouse", "slug": "amplitude"},
]

BESSEMER_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "twilio"},
    {"ats": "greenhouse", "slug": "sendgrid"},
    {"ats": "greenhouse", "slug": "shopify"},
    {"ats": "greenhouse", "slug": "toast"},
    {"ats": "greenhouse", "slug": "veeva"},
    {"ats": "greenhouse", "slug": "canva"},
    {"ats": "greenhouse", "slug": "pagerduty"},
    {"ats": "greenhouse", "slug": "procore"},
    {"ats": "greenhouse", "slug": "mindbody"},
    {"ats": "greenhouse", "slug": "gainsight"},
    {"ats": "greenhouse", "slug": "egnyte"},
    {"ats": "greenhouse", "slug": "contentsquare"},
]

INSIGHT_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "teamwork"},
    {"ats": "greenhouse", "slug": "sprinklr"},
    {"ats": "greenhouse", "slug": "optimizely"},
    {"ats": "greenhouse", "slug": "socure"},
    {"ats": "greenhouse", "slug": "freshworks"},
    {"ats": "greenhouse", "slug": "pluralsight"},
    {"ats": "greenhouse", "slug": "wrike"},       # moved from lever
    {"ats": "greenhouse", "slug": "egnyte"},
    {"ats": "greenhouse", "slug": "aqua-security"},
    {"ats": "greenhouse", "slug": "armis"},
]

BATTERY_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "glassdoor"},
    {"ats": "greenhouse", "slug": "bazaarvoice"},
    {"ats": "greenhouse", "slug": "angi"},
    {"ats": "greenhouse", "slug": "comscore"},
    {"ats": "greenhouse", "slug": "hubspot"},     # moved from lever
    {"ats": "greenhouse", "slug": "carbonblack"},
    {"ats": "greenhouse", "slug": "kustomer"},
    {"ats": "greenhouse", "slug": "forescout"},
]

VISTA_PORTFOLIO: list[dict] = [
    {"ats": "greenhouse", "slug": "marketo"},
    {"ats": "greenhouse", "slug": "cvent"},
    {"ats": "greenhouse", "slug": "datto"},
    {"ats": "greenhouse", "slug": "jamf"},        # moved from lever
    {"ats": "greenhouse", "slug": "apttus"},
    {"ats": "greenhouse", "slug": "solera"},
    {"ats": "greenhouse", "slug": "solarwinds"},  # moved from lever
    {"ats": "greenhouse", "slug": "ping-identity"},
    {"ats": "greenhouse", "slug": "episerver"},
]

# Unified list across all VCs — used by Greenhouse/Lever/Ashby scrapers.
ALL_VC_PORTFOLIO_SLUGS: list[dict] = (
    A16Z_PORTFOLIO
    + SEQUOIA_PORTFOLIO
    + BESSEMER_PORTFOLIO
    + INSIGHT_PORTFOLIO
    + BATTERY_PORTFOLIO
    + VISTA_PORTFOLIO
)

# VC portfolio board URLs (Getro / Consider powered).
# These are scraped in vc_boards_scraper.py as web pages.
# consider_id: the board ID used in the Consider API POST body
VC_BOARD_URLS: list[dict] = [
    {"name": "a16z Jobs", "url": "https://jobs.a16z.com/jobs", "type": "consider", "consider_id": "andreessen-horowitz"},
    {"name": "Sequoia Jobs", "url": "https://jobs.sequoiacap.com/jobs", "type": "consider", "consider_id": "sequoia-capital"},
    {"name": "Bessemer Jobs", "url": "https://jobs.bvp.com/jobs", "type": "consider", "consider_id": "bessemer-ventures"},
    {"name": "Battery Ventures Jobs", "url": "https://jobs.battery.com/jobs", "type": "consider", "consider_id": "battery-ventures"},
    {"name": "Lightspeed Jobs", "url": "https://jobs.lsvp.com/jobs", "type": "consider", "consider_id": "lightspeed"},
    {"name": "GV Jobs", "url": "https://jobs.gv.com/jobs", "type": "consider", "consider_id": "gv"},
    {"name": "First Round Jobs", "url": "https://jobs.firstround.com/jobs", "type": "consider", "consider_id": "first-round-capital"},
    {"name": "Insight Partners Jobs", "url": "https://jobs.insightpartners.com/jobs", "type": "getro"},
    {"name": "Vista Equity Jobs", "url": "https://vistaequitypartners.getro.com/jobs", "type": "getro"},
]
