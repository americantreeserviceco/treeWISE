"""Refresh the tree-care database from the public sources.

Each source is replaced in full on a successful fetch. A failed fetch leaves
the previous rows in place, prints the error, and makes the run exit with
status 1, so a scheduler can see it. Nothing is seeded with made-up records.
"""

import csv
import io
import sys
import zipfile
from datetime import datetime, timezone

import requests

import tree_care_common as common

ACS_VINTAGE = "2019-2023 ACS 5-year"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value):
    return None if value is None else str(value).strip()


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def etl_trees(conn):
    """Denver city street-tree inventory, all species.

    Loads every tree into street_trees and flags ash (botanical genus
    Fraxinus). vulnerable_trees is then rebuilt as the ash subset, so the EAB
    views keep working. Matching is on the genus, not on the word "ash" in the
    common name, which used to pull in "Flashfire" and "Washington".
    """
    print("\n[ETL] Denver street-tree inventory (all species)...")
    rows = common.fetch_socrata(common.TREE_INVENTORY_URL, order="objectid")
    if not rows:
        raise RuntimeError("tree inventory returned no rows")

    loaded = _now()
    seen = set()
    records = []
    for r in rows:
        tree_id = _text(r.get("objectid"))
        if not tree_id or tree_id in seen:
            continue
        seen.add(tree_id)
        genus = _text(r.get("species_botanic")) or ""
        records.append((
            tree_id,
            _text(r.get("species_common")),
            genus or None,
            _text(r.get("address")),
            _text(r.get("street")),
            _text(r.get("neighbor")),
            _text(r.get("condition")),
            _text(r.get("diameter")),
            _text(r.get("inventory_date")),
            _text(r.get("eab_tag")),
            _float(r.get("y_lat")),
            _float(r.get("x_long")),
            1 if genus.lower().startswith("fraxinus") else 0,
            0 if (not genus or genus.startswith("_")) else 1,
            loaded,
        ))

    conn.execute("DELETE FROM street_trees")
    conn.executemany(
        """
        INSERT INTO street_trees
          (tree_id, common_name, genus, address, street, neighbor, condition,
           diameter, inventory_date, eab_tag, latitude, longitude, is_ash, is_tree,
           loaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )

    conn.execute("DELETE FROM vulnerable_trees")
    conn.execute("""
        INSERT INTO vulnerable_trees
          (tree_id, common_name, genus, address, street, neighbor, condition,
           inventory_date, eab_tag, latitude, longitude, loaded_at)
        SELECT tree_id, common_name, genus, address, street, neighbor, condition,
               inventory_date, eab_tag, latitude, longitude, loaded_at
        FROM street_trees
        WHERE is_ash = 1
    """)
    ash = conn.execute("SELECT COUNT(*) FROM vulnerable_trees").fetchone()[0]
    print(
        f"Success [Trees]: loaded {len(records)} street trees;"
        f" {ash} are ash (Fraxinus)."
    )
    return len(records)


def etl_competitors(conn):
    """Colorado SOS registry: tree businesses in Good Standing in target cities."""
    print("\n[ETL] Colorado SOS tree-business registry...")
    rows = common.fetch_socrata(
        common.SOS_BUSINESS_URL,
        where=common.competitor_where_clause(),
    )
    if not rows:
        raise RuntimeError("SOS registry returned no matching rows")
    if not any("principalcity" in r for r in rows):
        # The API omits null fields per row, so check that the field exists
        # anywhere in the result before treating it as missing.
        raise RuntimeError("SOS rows have no principalcity field; not guessing")

    targets = set(common.TARGET_CITIES)
    kept = [
        r for r in rows
        if (_text(r.get("principalcity")) or "").upper() in targets
    ]
    loaded = _now()
    records = [
        (
            _text(r.get("entityid")),
            _text(r.get("entityname")),
            (_text(r.get("principalcity")) or "").upper() or None,
            _text(r.get("principaladdress1")),
            _text(r.get("principalzipcode")),
            _text(r.get("entitystatus")),
            _text(r.get("entityformdate")),
            loaded,
        )
        for r in kept
    ]
    conn.execute("DELETE FROM competitors")
    conn.executemany(
        """
        INSERT INTO competitors
          (entity_id, entity_name, principal_city, principal_address, principal_zip,
           status, initial_filing_date, loaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    print(
        f"Success [Competitors]: loaded {len(records)} tree businesses in"
        f" {len(targets)} target cities (from {len(rows)} statewide matches)."
    )
    return len(records)


def etl_foothills_data(conn):
    """Jefferson County open-space projects from ArcGIS. No fallback records."""
    print("\n[ETL] Jefferson County open-space projects (ArcGIS)...")
    data = common.get_json(
        common.FOOTHILL_PROJECTS_URL,
        params={"where": "1=1", "outFields": "*", "outSR": "4326", "f": "json"},
    )
    features = data.get("features", [])
    if not features:
        raise RuntimeError("ArcGIS returned no project features")

    loaded = _now()
    records = [
        (
            str(f.get("attributes", {}).get("OBJECTID", "")),
            _text(f.get("attributes", {}).get("ProjectName")),
            _text(f.get("attributes", {}).get("Status")),
            _text(f.get("attributes", {}).get("Description")),
            loaded,
        )
        for f in features
    ]
    conn.execute("DELETE FROM foothill_projects")
    conn.executemany(
        """
        INSERT INTO foothill_projects (object_id, project_name, status, description, loaded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        records,
    )
    print(f"Success [Foothills]: loaded {len(records)} projects.")
    return len(records)


def _census_by_zip(url, column):
    """Median values keyed by ZIP from one Census ACS bulk table."""
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from {url}")
    values = {}
    reader = csv.DictReader(io.StringIO(response.text), delimiter="|")
    for row in reader:
        geo = row.get("GEO_ID", "")
        if geo.startswith("860Z200US"):
            values[geo[-5:]] = common.parse_census_value(row.get(column))
    return values


def etl_zip_profile(conn):
    """Colorado ZIPs with distance from Golden and ACS medians (income, home value)."""
    print("\n[ETL] ZIP profile (Census ACS medians, ZCTA centroids)...")
    gaz = requests.get(common.ZCTA_GAZETTEER_URL, timeout=120)
    if gaz.status_code != 200:
        raise RuntimeError(f"gazetteer HTTP {gaz.status_code}")
    with zipfile.ZipFile(io.BytesIO(gaz.content)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".txt"))
        text = archive.read(name).decode("utf-8")
    centroids = {}
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = [h.strip() for h in next(reader)]
    geoid_i, lat_i, lon_i = (header.index(k) for k in ("GEOID", "INTPTLAT", "INTPTLONG"))
    for row in reader:
        zip_code = row[geoid_i].strip()
        if zip_code.isdigit() and 80001 <= int(zip_code) <= 81658:
            centroids[zip_code] = (float(row[lat_i]), float(row[lon_i]))
    if not centroids:
        raise RuntimeError("no Colorado ZCTAs found in the gazetteer")

    income = _census_by_zip(common.CENSUS_HH_INCOME_URL, "B19013_E001")
    home = _census_by_zip(common.CENSUS_HOME_VALUE_URL, "B25077_E001")
    if not income or not home:
        raise RuntimeError("Census tables returned no ZCTA rows")

    loaded = _now()
    records = []
    for zip_code, (lat, lon) in centroids.items():
        records.append((
            zip_code,
            lat,
            lon,
            round(common.miles_from_golden(lat, lon), 1),
            income.get(zip_code),
            home.get(zip_code),
            ACS_VINTAGE,
            loaded,
        ))
    conn.execute("DELETE FROM zip_profile")
    conn.executemany(
        """
        INSERT INTO zip_profile
          (zip, latitude, longitude, miles_from_golden, median_hh_income,
           median_home_value, acs_vintage, loaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    print(
        f"Success [ZIP profile]: {len(records)} Colorado ZIPs;"
        f" {sum(1 for r in records if r[4] is not None)} with income,"
        f" {sum(1 for r in records if r[5] is not None)} with home value."
    )
    return len(records)


def main():
    print("Starting Tree Care Business Intelligence Pipeline...")
    print(f"Database: {common.DB_PATH}")
    conn = common.connect()
    failures = []
    for step in (etl_trees, etl_competitors, etl_foothills_data, etl_zip_profile):
        try:
            with conn:  # one transaction per source
                step(conn)
        except Exception as exc:  # keep going so one bad source doesn't block the rest
            failures.append((step.__name__, exc))
            print(f"FAILED {step.__name__}: {exc}", file=sys.stderr)
    conn.close()

    if failures:
        print(
            f"\nPipeline finished with {len(failures)} failed source(s);"
            " previous data kept for those.",
            file=sys.stderr,
        )
        return 1
    print("\nPipeline finished: all sources loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
