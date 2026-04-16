# Exact target titles — used for fuzzy matching against scraped results.
# The fuzzy threshold is 85/100 (rapidfuzz WRatio).
TARGET_TITLES = [
    "Head of AI",
    "Head of AI Strategy",
    "Head of AI Strategy & Transformation",
    "Head of Artificial Intelligence",
    "VP of AI",
    "VP AI",
    "VP AI Strategy",
    "VP AI Enablement",
    "VP AI Transformation",
    "Vice President of AI",
    "Vice President AI Strategy",
    "Director of AI Transformation",
    "Director AI Strategy",
    "Director of AI",
    "Director of Artificial Intelligence",
    "Chief AI Officer",
    "CAIO",
    "GM of AI",
    "General Manager AI",
    "General Manager of AI",
    "GM Artificial Intelligence",
    "Head of AI Products",
    "Head of AI Enablement",
    "VP of AI Products",
    "VP of Artificial Intelligence",
    "Director of Digital Transformation",
    "VP of Digital Transformation",
    "Vice President of Digital Transformation",
    "Head of Digital Transformation",
    "Director Digital Transformation",
    "VP Digital Transformation",
    "Head Digital Transformation",
]

# If any of these strings appear in the scraped title it's an automatic
# include (case-insensitive substring match, runs before fuzzy matching).
TITLE_INCLUDE_KEYWORDS = [
    "head of ai",
    "vp of ai",
    "vp ai",
    "director of ai",
    "director ai",
    "chief ai",
    "caio",
    "gm of ai",
    "gm ai",
    "general manager ai",
    "head of artificial intelligence",
    "vp artificial intelligence",
    "digital transformation",
]

# Fuzzy match score threshold (0-100).
TITLE_FUZZY_THRESHOLD = 82

# Short search terms submitted to job boards (a subset of TARGET_TITLES
# chosen to maximise recall without excessive API calls).
_SEARCH_TERMS = [
    "Head of AI",
    "VP of AI",
    "VP AI Strategy",
    "Director of AI Transformation",
    "Chief AI Officer",
    "GM of AI",
    "Head of Digital Transformation",
    "VP of Digital Transformation",
    "Director of Digital Transformation",
]
