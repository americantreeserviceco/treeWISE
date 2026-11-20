"""Shared paths, config, HTTP helpers and database schema for the tree-care tools.

Every script imports from here so paths, city lists and the schema are defined
once. Nothing here writes data on import.
"""

import datetime
import math
import os
import sqlite3
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tree_care_intelligence.db"

# Golden, Colorado: the business base.
GOLDEN_LAT = 39.7555
GOLDEN_LON = -105.2211

# NWS forecast grid for Golden (verified against api.weather.gov/points).
NWS_OFFICE = "BOU"
NWS_GRID_X = 55
NWS_GRID_Y = 63

# Socrata datasets on data.colorado.gov.
TREE_INVENTORY_URL = "https://data.colorado.gov/resource/wz8h-dap6.json"
SOS_BUSINESS_URL = "https://data.colorado.gov/resource/4ykn-tg5h.json"

# ArcGIS layer for Jefferson County open-space projects.
FOOTHILL_PROJECTS_URL = (
    "https://services.arcgis.com/XG15cJsnqnnWdsOV/arcgis/rest/services/"
    "JCPOS_Active_Projects/FeatureServer/0/query"
)

# Cities the business serves plus the Northern Colorado cities the original
# pipeline already tracked. Compared case-insensitively against principalcity.
TARGET_CITIES = [
    # Service cities (american tree colorado site)
    "GOLDEN",
    "DENVER",
    "BOULDER",
    "ARVADA",
    "LAKEWOOD",
    "HIGHLANDS RANCH",
    # Existing Northern Colorado list
    "LONGMONT",
    "LOVELAND",
    "FORT COLLINS",
    "ERIE",
    "LAFAYETTE",
    "LOUISVILLE",
    "EVERGREEN",
    "FIRESTONE",
    "FREDERICK",
]

# Name phrases that identify tree businesses in the SOS registry. Phrases are
# used instead of bare "tree" so names like "Street" or "Entree" don't match.
COMPETITOR_NAME_PHRASES = [
    "tree service",
    "tree care",
    "tree removal",
    "tree trim",
    "tree experts",
    "tree surgery",
    "tree company",
    "tree & landscape",
    "tree and landscape",
    "arbor",
    "forestry",
]

# Census ACS 5-year 2019–2023 bulk tables (public, no key). Rows are keyed by
# GEO_ID "860Z200US<ZIP>" for ZCTAs.
CENSUS_HH_INCOME_URL = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2023/"
    "table-based-SF/data/5YRData/acsdt5y2023-b19013.dat"
)
CENSUS_HOME_VALUE_URL = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2023/"
    "table-based-SF/data/5YRData/acsdt5y2023-b25077.dat"
)
# Census 2023 ZCTA gazetteer: internal point (lat/lon) per ZIP.
ZCTA_GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/"
    "2023_Gaz_zcta_national.zip"
)

# NOAA GHCN-Daily station files, tried in order. The first one with enough
# valid days in the 30-day window is used. CoCoRaHS gauges in Golden first,
# then Denver International Airport as a complete but more distant backup.
PRECIP_STATIONS = [
    "US1COJF0611",  # GOLDEN 0.8 NE (CoCoRaHS)
    "US1COJF0620",  # GOLDEN 3.5 WSW (CoCoRaHS)
    "US1COJF0563",  # GOLDEN 1.2 E (CoCoRaHS)
    "USW00003017",  # Denver International Airport (~30 mi)
]
NOAA_DLY_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station}.dly"
PRECIP_WINDOW_DAYS = 30
PRECIP_MIN_VALID_DAYS = 20

SOCRATA_PAGE_SIZE = 50000
HTTP_TIMEOUT = 30


class ConfigError(RuntimeError):
    pass


def nws_contact():
    """Contact string for the NWS User-Agent header.

    NWS asks for a real contact. Set TREE_CARE_CONTACT in the environment
    (for example an email address you control). Refuses to run without it
    rather than sending a placeholder.
    """
    value = os.environ.get("TREE_CARE_CONTACT", "").strip()
    if not value:
        raise ConfigError(
            "Set the TREE_CARE_CONTACT environment variable to a real contact"
            " address before calling the NWS API."
        )
    return value


def get_json(url, params=None, headers=None):
    """GET a JSON document. Raises on network errors and non-200 responses."""
    response = requests.get(
        url, params=params, headers=headers, timeout=HTTP_TIMEOUT
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code} from {url}: {response.text[:200]}"
        )
    return response.json()


def fetch_socrata(url, where=None, select=None, order=None):
    """Fetch every row matching a SoQL filter, paging past the 1,000-row default.

    Pass `order` (a stable unique column, e.g. "objectid") when paging a large
    dataset, so pages don't overlap or skip rows.
    """
    rows = []
    offset = 0
    while True:
        params = {"$limit": SOCRATA_PAGE_SIZE, "$offset": offset}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order
        page = get_json(url, params=params)
        rows.extend(page)
        if len(page) < SOCRATA_PAGE_SIZE:
            return rows
        offset += SOCRATA_PAGE_SIZE


def competitor_where_clause():
    phrases = " OR ".join(
        f"lower(entityname) like '%{phrase}%'" for phrase in COMPETITOR_NAME_PHRASES
    )
    return f"({phrases}) AND entitystatus='Good Standing'"


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_missing_columns(conn, table, columns):
    existing = _columns(conn, table)
    for name, col_type in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")


def init_schema(conn):
    """Create tables and add any columns missing from an older database.

    Only additive changes: existing rows are kept.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vulnerable_trees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tree_id TEXT,
            common_name TEXT,
            genus TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    _add_missing_columns(conn, "vulnerable_trees", [
        ("street", "TEXT"),
        ("neighbor", "TEXT"),
        ("condition", "TEXT"),
        ("inventory_date", "TEXT"),
        ("eab_tag", "TEXT"),
        ("loaded_at", "DATETIME"),
    ])

    # Full Denver street-tree inventory, all species. vulnerable_trees is the
    # ash subset (is_ash = 1) of this table.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS street_trees (
            tree_id TEXT PRIMARY KEY,
            common_name TEXT,
            genus TEXT,
            address TEXT,
            street TEXT,
            neighbor TEXT,
            condition TEXT,
            diameter TEXT,
            inventory_date TEXT,
            eab_tag TEXT,
            latitude REAL,
            longitude REAL,
            is_ash INTEGER,
            loaded_at DATETIME
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_street_trees_ash ON street_trees (is_ash)"
    )
    # is_tree = 0 for vacant sites and other placeholder rows (genus starts
    # with "_" or is blank). Exclude them from any tree counts.
    _add_missing_columns(conn, "street_trees", [("is_tree", "INTEGER")])

    conn.execute("""
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT,
            entity_name TEXT,
            principal_city TEXT,
            status TEXT,
            initial_filing_date TEXT
        )
    """)
    _add_missing_columns(conn, "competitors", [
        ("principal_address", "TEXT"),
        ("principal_zip", "TEXT"),
        ("loaded_at", "DATETIME"),
    ])

    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            period_name TEXT,
            temperature INTEGER,
            conditions TEXT,
            fertilization_recommended BOOLEAN
        )
    """)
    _add_missing_columns(conn, "weather_triggers", [
        ("forecast_start", "TEXT"),
        ("precip_30d_in", "REAL"),
        ("precip_station", "TEXT"),
        ("precip_days", "INTEGER"),
    ])
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_weather_period
        ON weather_triggers (period_name, forecast_start)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS foothill_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            object_id TEXT,
            project_name TEXT,
            status TEXT,
            description TEXT
        )
    """)
    _add_missing_columns(conn, "foothill_projects", [("loaded_at", "DATETIME")])

    # One row per ZIP (Colorado ZCTAs): location, distance from Golden, medians.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zip_profile (
            zip TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            miles_from_golden REAL,
            median_hh_income INTEGER,
            median_home_value INTEGER,
            acs_vintage TEXT,
            loaded_at DATETIME
        )
    """)
    conn.commit()


def miles_from_golden(lat, lon):
    """Great-circle distance in miles from the Golden base."""
    if lat is None or lon is None:
        return None
    radius = 3958.8
    la1, lo1 = math.radians(GOLDEN_LAT), math.radians(GOLDEN_LON)
    la2, lo2 = math.radians(lat), math.radians(lon)
    a = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def precip_window_inches(as_of, days=PRECIP_WINDOW_DAYS):
    """Total precipitation in inches over the last `days` days up to `as_of`.

    Reads NOAA GHCN-Daily station files in PRECIP_STATIONS order and uses the
    first station with at least PRECIP_MIN_VALID_DAYS reported days. Returns
    (inches, station, valid_days), or (None, None, 0) if no station qualifies.
    """
    start = as_of - datetime.timedelta(days=days - 1)
    for station in PRECIP_STATIONS:
        response = requests.get(
            NOAA_DLY_URL.format(station=station), timeout=HTTP_TIMEOUT
        )
        if response.status_code != 200:
            continue
        total_tenths_mm = 0
        valid = 0
        for line in response.text.splitlines():
            if line[17:21] != "PRCP":
                continue
            year, month = int(line[11:15]), int(line[15:17])
            for day in range(1, 32):
                offset = 21 + 8 * (day - 1)
                try:
                    date = datetime.date(year, month, day)
                except ValueError:
                    continue
                if not (start <= date <= as_of):
                    continue
                value = int(line[offset:offset + 5])
                if value == -9999:
                    continue
                valid += 1
                total_tenths_mm += value
        if valid >= PRECIP_MIN_VALID_DAYS:
            inches = total_tenths_mm / 10 / 25.4
            return round(inches, 2), station, valid
    return None, None, 0


def parse_census_value(text):
    """Census bulk values are numbers, or codes like '-' or '250000+'."""
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


def connect():
    """Open the project database with the schema in place."""
    conn = sqlite3.connect(DB_PATH)
    init_schema(conn)
    return conn
