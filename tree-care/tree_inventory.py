"""Export the Denver ash-tree inventory to CSV for treatment planning.

Writes ash_trees_eab_targets.csv next to this script. Same filter as the
pipeline: botanical genus Fraxinus, all pages.
"""

import sys

import pandas as pd

import tree_care_common as common


def export_ash_trees():
    rows = common.fetch_socrata(
        common.TREE_INVENTORY_URL,
        where="lower(species_botanic) like 'fraxinus%'",
    )
    if not rows:
        raise RuntimeError("no ash rows returned")

    df = pd.DataFrame(rows).drop_duplicates(subset=["objectid"])
    output = common.BASE_DIR / "ash_trees_eab_targets.csv"
    df.to_csv(output, index=False)
    print(f"Saved {len(df)} unique ash trees to {output}")
    return df


if __name__ == "__main__":
    try:
        export_ash_trees()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
