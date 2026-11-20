"""Check the Golden forecast and record fertilization / watering windows.

Rule in use (an assumption, to be confirmed by the crew lead). A forecast
period is OPEN when all three hold:
  1. forecast air temperature is above 40 F,
  2. the forecast text does not mention snow,
  3. precipitation over the last 30 days is under 1.00 inch, measured at the
     nearest Golden-area NOAA station with enough reported days (falls back to
     Denver International Airport). If no station qualifies, the period holds.

Not checked yet: soil temperature and frost depth.

Each run upserts one row per forecast period into weather_triggers, so repeated
runs update the same rows rather than duplicating them.

Needs TREE_CARE_CONTACT set to a real contact address (NWS requirement).
"""

import datetime
import sys

import tree_care_common as common

TEMP_THRESHOLD_F = 40
PRECIP_THRESHOLD_IN = 1.00


def window_open(period, precip_in):
    temp = period.get("temperature")
    text = (period.get("shortForecast") or "").lower()
    return (
        period.get("temperatureUnit") == "F"
        and temp is not None
        and temp > TEMP_THRESHOLD_F
        and "snow" not in text
        and precip_in is not None
        and precip_in < PRECIP_THRESHOLD_IN
    )


def check_winter_fertilization_conditions():
    contact = common.nws_contact()
    url = (
        f"https://api.weather.gov/gridpoints/{common.NWS_OFFICE}/"
        f"{common.NWS_GRID_X},{common.NWS_GRID_Y}/forecast"
    )
    headers = {
        "User-Agent": f"(tree-care-app, {contact})",
        "Accept": "application/ld+json",
    }
    data = common.get_json(url, headers=headers)
    # The ld+json response puts periods at the top level; the GeoJSON form
    # nests them under "properties". Accept either.
    periods = (data.get("periods") or data.get("properties", {}).get("periods") or [])[:6]
    if not periods:
        raise RuntimeError("NWS returned no forecast periods")

    precip_in, station, valid_days = common.precip_window_inches(
        datetime.date.today()
    )

    conn = common.connect()
    with conn:
        for period in periods:
            is_open = window_open(period, precip_in)
            conn.execute(
                """
                INSERT INTO weather_triggers
                  (period_name, forecast_start, temperature, conditions,
                   fertilization_recommended, precip_30d_in, precip_station, precip_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (period_name, forecast_start) DO UPDATE SET
                  temperature = excluded.temperature,
                  conditions = excluded.conditions,
                  fertilization_recommended = excluded.fertilization_recommended,
                  precip_30d_in = excluded.precip_30d_in,
                  precip_station = excluded.precip_station,
                  precip_days = excluded.precip_days,
                  timestamp = CURRENT_TIMESTAMP
                """,
                (
                    period.get("name"),
                    period.get("startTime"),
                    period.get("temperature"),
                    period.get("shortForecast"),
                    1 if is_open else 0,
                    precip_in,
                    station,
                    valid_days,
                ),
            )
    conn.close()

    if precip_in is None:
        precip_text = "unknown (no station had enough reported days; all periods hold)"
    else:
        precip_text = f"{precip_in:.2f} in from {station} ({valid_days} days reported)"
    print("\n--- Golden winter windows ---")
    print(f"30-day precipitation: {precip_text}")
    for period in periods:
        state = "OPEN" if window_open(period, precip_in) else "hold"
        print(
            f"[{period.get('name')}] {period.get('temperature')}°"
            f"{period.get('temperatureUnit')} | {period.get('shortForecast')}"
            f" | {state}"
        )
    print(f"\nUpserted {len(periods)} forecast period(s) in weather_triggers.")


if __name__ == "__main__":
    try:
        check_winter_fertilization_conditions()
    except (common.ConfigError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
