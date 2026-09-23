# Private application seeds

These files provide the application's initial registry, billing records and risk catalog.
Registry and billing seeds are imported into the server's SQLite database on first startup.
They must not be copied to Vite public assets or a public static download directory.

- `bills.json`, `stations.json`: original 368-contract application data, moved out of `front/public`.
- `locations.json`: 75 original meter coordinates; bootstrap groups them by physical station.
- `details_long.csv`: user-provided historical detailed billing data from the previous `withus` project.
  It augments existing bills by customer, billing month and bill type, preserving existing-only history.
  Rows without a detailed payment amount remain present with null amounts and
  `detail_available: false`, never replaced with zero.
- `meter_collection.csv`: reviewed initial daily/bill-only collection settings and exact bill names.
- `risk/test_anomalies.csv`: the canonical initial risk dataset (11,285 rows), preserved from
  the previous model results. Runtime snapshots supersede it after publication; the app
  does not read archived experiments.

Seed migrations run once and preserve subsequent registry changes. Current 80-meter review notes
and usage purposes come from `data/billing/mkey_station_map.csv` and `meter_match.csv`.
Additional review XLSX files are imported only when explicitly passed to
`python -m back.api.import_data --review /path/review.xlsx`.

These are structured source records, not original Arisu PDF notices. Generated PDFs say so.

Previous analysis and model output directories are preserved under
[`archive/`](../../archive/README.md). They are separate from these active seed files.
