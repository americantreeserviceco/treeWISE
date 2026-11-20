"""Check that each data source answers and has the fields the pipeline uses."""

import sys

import tree_care_common as common

EXPECTED = {
    "Tree inventory": (
        common.TREE_INVENTORY_URL,
        {"objectid", "species_botanic", "species_common", "street", "y_lat", "x_long"},
        "lower(species_botanic) like 'fraxinus%'",
    ),
    "SOS registry": (
        common.SOS_BUSINESS_URL,
        {"entityid", "entityname", "principalcity", "principaladdress1", "principalzipcode"},
        "principalcity is not null",
    ),
}


def check_socrata(label, url, expected_fields, where=None):
    print(f"\n--- {label} ---")
    params = {"$limit": 5}
    if where:
        params["$where"] = where  # sample rows that have the fields set
    try:
        rows = common.get_json(url, params=params)
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return False
    if not rows:
        print("FAILED: no rows returned")
        return False
    seen = set().union(*(set(r.keys()) for r in rows))
    missing = expected_fields - seen
    print(f"Rows: {len(rows)}")
    if missing:
        print(f"FAILED: fields not found: {sorted(missing)}")
        return False
    print("OK: expected fields present")
    return True


def check_arcgis():
    print("\n--- Jefferson County projects (ArcGIS) ---")
    try:
        data = common.get_json(
            common.FOOTHILL_PROJECTS_URL,
            params={"where": "1=1", "outFields": "*", "outSR": "4326", "f": "json"},
        )
    except RuntimeError as exc:
        print(f"FAILED: {exc}")
        return False
    features = data.get("features", [])
    print(f"Features: {len(features)}")
    return bool(features)


def check_nws():
    print("\n--- NWS forecast (Golden grid) ---")
    try:
        headers = {
            "User-Agent": f"(tree-care-app, {common.nws_contact()})",
            "Accept": "application/ld+json",
        }
        data = common.get_json(
            f"https://api.weather.gov/gridpoints/{common.NWS_OFFICE}/"
            f"{common.NWS_GRID_X},{common.NWS_GRID_Y}/forecast",
            headers=headers,
        )
    except (common.ConfigError, RuntimeError) as exc:
        print(f"FAILED: {exc}")
        return False
    periods = data.get("properties", {}).get("periods", [])
    print(f"Forecast periods: {len(periods)}")
    return bool(periods)


if __name__ == "__main__":
    results = [
        check_socrata(label, url, fields, where)
        for label, (url, fields, where) in EXPECTED.items()
    ]
    results.append(check_arcgis())
    results.append(check_nws())
    sys.exit(0 if all(results) else 1)
