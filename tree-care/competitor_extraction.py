"""Export tree-business competitors in the target cities to CSV.

Writes noco_tree_service_competitors.csv next to this script. Uses the same
name phrases and city list as the pipeline, so the two cannot drift apart.
"""

import sys

import pandas as pd

import tree_care_common as common


def export_tree_competitors():
    rows = common.fetch_socrata(
        common.SOS_BUSINESS_URL,
        where=common.competitor_where_clause(),
    )
    if not rows:
        raise RuntimeError("no matching registry rows returned")

    df = pd.DataFrame(rows)
    if "principalcity" not in df.columns:
        # Refuse rather than export every statewide match as if it were local.
        raise RuntimeError("registry rows have no principalcity field")

    targets = set(common.TARGET_CITIES)
    df = df[df["principalcity"].fillna("").str.upper().str.strip().isin(targets)]
    df = df.drop_duplicates(subset=["entityid"])

    output = common.BASE_DIR / "noco_tree_service_competitors.csv"
    df.to_csv(output, index=False)
    print(f"Saved {len(df)} tree competitors in target cities to {output}")
    return df


if __name__ == "__main__":
    try:
        export_tree_competitors()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
