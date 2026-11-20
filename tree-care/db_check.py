"""Print row and unique-key counts for each table in the project database.

Duplicates show up as rows greater than unique keys.
"""

import sqlite3

import tree_care_common as common

CHECKS = [
    ("street_trees", "tree_id"),
    ("vulnerable_trees", "tree_id"),
    ("competitors", "entity_id"),
    ("foothill_projects", "object_id"),
    ("weather_triggers", "period_name, forecast_start"),
]


def main():
    conn = sqlite3.connect(common.DB_PATH)
    print(f"Database: {common.DB_PATH}")
    for table, key in CHECKS:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        unique = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT DISTINCT {key} FROM {table})"
        ).fetchone()[0]
        flag = "  <- duplicates" if total > unique else ""
        print(f"Table '{table}': {total} rows, {unique} unique by ({key}){flag}")
    conn.close()


if __name__ == "__main__":
    main()
