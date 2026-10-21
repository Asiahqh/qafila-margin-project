"""Qafila gross margin pipeline: raw files -> DuckDB -> dbt -> Iceberg.

    uv run python run.py --data-dir data --warehouse warehouse

Must work on an empty warehouse folder, and must be safe to run again on the same one.
The grader runs it on a dataset you haven't seen, so never hard-code file names, row counts or SKUs.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import duckdb
from pyiceberg.catalog.sql import SqlCatalog

DBT_DIR = Path(__file__).resolve().parent / "dbt"


def get_catalog(warehouse: Path) -> SqlCatalog:
    """The Iceberg catalog the grader reads. Don't change the name, the URI or the warehouse."""
    warehouse.mkdir(parents=True, exist_ok=True)
    return SqlCatalog(
        "qafila",
        uri=f"sqlite:///{(warehouse / 'catalog.db').as_posix()}",
        warehouse=warehouse.resolve().as_posix(),
    )


def ingest(data_dir: Path, db: Path) -> None:
    """Load SQLite tables and supplier CSV files into DuckDB raw schema.

    Replacing raw tables makes repeated ingestion safe.
    """
    source_db = data_dir / "qafila_oltp.sqlite"
    supplier_dir = data_dir / "suppliers"

    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")

      
        with sqlite3.connect(str(source_db)) as source:
            for table in ("orders", "order_items", "products", "stores"):
                cursor = source.execute(f'SELECT * FROM "{table}"')
                columns = [column[0] for column in cursor.description]

                con.execute(f'DROP TABLE IF EXISTS raw."{table}"')

                column_definitions = ", ".join(
                    f'"{column}" VARCHAR' for column in columns
                )
                con.execute(
                    f'CREATE TABLE raw."{table}" ({column_definitions})'
                )

                import pyarrow as pa

                while True:
                    rows = cursor.fetchmany(10000)
                    if not rows:
                        break

                    batch = pa.table({
                        column: [
                            None if row[i] is None else str(row[i])
                            for row in rows
                        ]
                        for i, column in enumerate(columns)
                    })

                    con.register("batch_data", batch)
                    con.execute(
                        f'INSERT INTO raw."{table}" SELECT * FROM batch_data'
                    )
                    con.unregister("batch_data")

        
        price_files = sorted(supplier_dir.glob("prices_*.csv"))

        if not price_files:
            raise FileNotFoundError(
                f"No supplier price files found in {supplier_dir}"
            )

        file_paths = [str(path.resolve()) for path in price_files]

        con.execute("DROP TABLE IF EXISTS raw.supplier_prices")

        con.execute(
            """
            CREATE TABLE raw.supplier_prices AS
            SELECT
                * EXCLUDE (filename),
                regexp_extract(filename, '[^/\\\\]+$', 0) AS source_file
            FROM read_csv(
                ?,
                union_by_name = true,
                all_varchar = true,
                filename = true
            )
            """,
            [file_paths],
        )

        print("Raw data loaded successfully.")


def transform(db: Path) -> None:
    """Steps 2-4: build and test the dbt project in dbt/ against the DuckDB file.

    dbt runs in its own process: in this one it would keep the DuckDB file open and block publish().
    """
    env = {**os.environ, "QAFILA_DUCKDB": str(db.resolve())}
    cmd = [
        sys.executable,
        "-c",
        "from dbt.cli.main import cli; cli()",
        "build",
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
    ]

    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("dbt build failed")


def publish(db: Path, warehouse: Path) -> None:
    """Step 5: publish the three dbt models to Iceberg.

    silver.product_cost_history
    gold.weekly_margin
    quality.price_quarantine

    Existing tables must be updated in place to preserve snapshots.
    """
    import pyarrow as pa
    catalog = get_catalog(warehouse)

    tables = {
        "silver.product_cost_history": "silver.product_cost_history",
        "gold.weekly_margin": "gold.weekly_margin",
        "quality.price_quarantine": "quality.price_quarantine",
    }

    with duckdb.connect(str(db), read_only=True) as con:
        for iceberg_name, dbt_name in tables.items():
            namespace = iceberg_name.split(".")[0]
            catalog.create_namespace_if_not_exists(namespace)

            arrow_table = con.execute(
                f"SELECT * FROM {dbt_name}"
            ).fetch_arrow_table()

            identifier = tuple(iceberg_name.split("."))

            if catalog.table_exists(identifier):
                table = catalog.load_table(identifier)
                old_data = table.scan().to_arrow()

                if old_data.sort_by([(name, "ascending") for name in old_data.column_names]).equals(arrow_table.sort_by([(name, "ascending") for name in arrow_table.column_names])):
                    print(f"Unchanged: {iceberg_name}")
                    continue

                table.overwrite(arrow_table)
            else:
                catalog.create_table(
                    identifier,
                    schema=arrow_table.schema,
                ).append(arrow_table)

            print(f"Published: {iceberg_name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--warehouse", type=Path, default=Path("warehouse"))
    args = ap.parse_args()

    args.warehouse.mkdir(parents=True, exist_ok=True)
    db = args.warehouse / "qafila.duckdb"

    ingest(args.data_dir, db)
    transform(db)
    publish(db, args.warehouse)

    print(f"done: {args.warehouse.resolve()}")


if __name__ == "__main__":
    main()