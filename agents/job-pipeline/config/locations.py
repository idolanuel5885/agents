from typing import NamedTuple


class City(NamedTuple):
    name: str
    state: str
    state_abbr: str
    # Aliases used to normalise scraped location strings
    aliases: tuple[str, ...]


ALLOWED_CITIES = [
    City("Austin", "Texas", "TX", ("austin, tx", "austin, texas", "austin tx")),
    City("Portland", "Oregon", "OR", ("portland, or", "portland, oregon", "portland or")),
    City("Nashville", "Tennessee", "TN", ("nashville, tn", "nashville, tennessee", "nashville tn")),
    City("Denver", "Colorado", "CO", ("denver, co", "denver, colorado", "denver co")),
    City("Boulder", "Colorado", "CO", ("boulder, co", "boulder, colorado", "boulder co")),
]

# Strings that indicate a US-remote position when found in location fields.
REMOTE_INDICATORS = [
    "remote",
    "remote us",
    "us remote",
    "united states",
    "usa",
    "anywhere in the us",
    "work from anywhere",
    "fully remote",
    "remote (us)",
    "remote - us",
    "remote, us",
    "remote united states",
    "remote (united states)",
]

# Strings that indicate a non-US remote position — exclude these.
NON_US_REMOTE_BLOCKLIST = [
    "remote (uk)",
    "remote (europe)",
    "remote (eu)",
    "remote - uk",
    "remote - europe",
    "uk only",
    "europe only",
    "apac",
    "latam",
    "canada only",
]
