"""Check which tree-related registry names the competitor phrase list misses.

Pulls every Good Standing registry entity in the target cities whose name
contains a broader tree or landscape word, then marks whether the current
phrase list (COMPETITOR_NAME_PHRASES) would catch it. Writes the unmatched
ones to competitor_coverage_review.csv for a manual look. Nothing is loaded
into the database.
"""

import re
import sys

import pandas as pd

import tree_care_common as common

# Word starts only, so "street" does not match "tree" and "Forest Street" is
# still caught as a name but then removed by the exclusion below.
BROAD_WORDS = re.compile(
    r"\b(?:tree|arbor|forest|stump|prun|landscap|lawn|timber|canopy|orchard)",
    re.IGNORECASE,
)
# Names that are clearly not tree businesses (HOAs, churches, schools, etc.).
# Names that are clearly not tree businesses (HOAs, churches, schools, etc.).
# Landscape and lawn firms are excluded too: they are not competitors.
NOT_BUSINESS = re.compile(
    r"homeowner|association|condominium|condo|church|school|lodge|liquor|"
    r"apartment|community|owners|\bhoa\b|street|st\.? |landscap|lawn|sprinkler",
    re.IGNORECASE,
)


def matched_by_phrase(name):
    lowered = (name or "").lower()
    return any(phrase in lowered for phrase in common.COMPETITOR_NAME_PHRASES)


def main():
    cities = ", ".join(f"'{c}'" for c in common.TARGET_CITIES)
    rows = common.fetch_socrata(
        common.SOS_BUSINESS_URL,
        where=f"entitystatus='Good Standing' AND upper(principalcity) in ({cities})",
        order="entityid",
    )
    if not rows:
        raise RuntimeError("no Good Standing entities returned for the target cities")

    df = pd.DataFrame(rows).drop_duplicates(subset=["entityid"])
    df["entityname"] = df["entityname"].fillna("")
    is_broad = df["entityname"].str.contains(BROAD_WORDS) & ~df["entityname"].str.contains(NOT_BUSINESS)
    broad = df[is_broad].copy()
    broad["caught_now"] = broad["entityname"].map(matched_by_phrase)
    missed = broad[~broad["caught_now"]]

    output = common.BASE_DIR / "competitor_coverage_review.csv"
    missed[[
        "entityid", "entityname", "principalcity", "principalzipcode",
        "principaladdress1",
    ]].to_csv(output, index=False)

    print(f"Good Standing entities in target cities: {len(df)}")
    print(f"Broad tree/landscape name matches: {len(broad)}")
    print(f"Caught by current phrase list: {int(broad['caught_now'].sum())}")
    print(f"Not caught (review): {len(missed)} -> {output}")
    if not missed.empty:
        print("\nSample of unmatched names:")
        for name in missed["entityname"].head(15):
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
