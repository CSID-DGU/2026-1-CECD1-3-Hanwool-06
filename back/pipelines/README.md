# Private collection and model refresh

This directory contains the active pipelines. Retired collectors, ETL scripts and
saved experiments are catalogued in [`archive/README.md`](../../archive/README.md).
Archived files are not runtime inputs. The initial risk dataset is maintained at
`data/app_seed/risk/test_anomalies.csv`; new model results belong to `APP_DATA_DIR/model`.

All collection uses registered contracts from the application database. Archived and
inactive contracts are excluded. The API's incremental worker probes both daily readings
and bills for active Arisu contracts, including newly registered bill-only contracts.
The explicit range CLI uses `daily_enabled` for daily water/ridership collection.
Other providers remain visible in the catalog but are not sent to Arisu.

The web server owns the daily schedule (default 08:00 Asia/Seoul, configurable by a
superadmin), persisted jobs, and manual updates. Registration/restoration queues a
connection check automatically. A job shares one authenticated Arisu session across
its meters. Empty results are not proof of an invalid customer number. Source records
must identify the requested customer before a connection is verified. Errors and empty
responses never delete previous values. The same customer cannot be registered twice.
For a connection test, update an existing meter or use a separate temporary database.

Incremental collection fills missing dates, rechecks the recent three months and recent
bill months, and probes the past twelve months for a new customer. Older empty water
months are retried weekly. New observations publish a snapshot; risk evaluation keeps
its prior date until a model refresh. The Arisu update does not call the ridership API
or train the model. Use the explicit CLI below for those operations.

The current Arisu login uses the site's issued CSRF token and `mbrId`/`pwd` form.
The account's registered customer list is checked for daily readings only. Public bills
use customer number and the exact registered name, independently of member registration.
A daily access failure does not prevent bill collection. Historical JSON readings and the latest unbilled
JSON readings are merged by observation date, through the last completed day.
Identical readings repeated in different billing periods are kept once; conflicting
observations and mismatched customer responses fail validation. Levy pages are
paginated, and invalid cached customer/date records are fetched again.

Configure `ARISU_USER_ID`, `ARISU_USER_PWD`, and `SEOUL_PSGR_KEY` in the server environment
or root `.env`. Environment values take priority. Legacy `I121_USER_ID/I121_USER_PWD`
are accepted only as a credential fallback. No credentials are needed for fixture tests.

```sh
python -m pip install -r back/api/requirements.txt -r back/pipelines/requirements.txt
python -m back.pipelines.refresh --start 2026-06-01 --end 2026-06-30 --water --ridership
python -m back.pipelines.refresh --start 2026-06-01 --end 2026-08-31 --bills
python -m back.pipelines.refresh --model
python -m back.pipelines.refresh --all
python -m unittest discover -s tests -p test_pipeline.py
```

LightGBM also needs an OpenMP runtime. On macOS install `libomp` or configure the
existing environment's library directory; Python dependencies alone do not supply it.

The default interval is the recent five completed KST dates. `--model` reads existing
local observations; collection only runs for explicitly selected sources. Missing
credentials fail the selected collection, without changing the last published snapshot.

Raw readings, successful partial results, per-date status files, datasets and model
results are under `APP_DATA_DIR` (default `data/runtime`). A missing/failed fetch never
writes zero usage or replaces previous observations with an empty file. Monthly water
queries are reused across the requested range. CSV upserts use customer number + date;
regular and supplementary bills retain separate keys. Retry the same range to fill
missing observations safely. A date's status distinguishes fresh completeness from
older rows retained after a failed request.

`refresh_report.json` records selected steps and failures. `snapshot/manifest.json`
points to one immutable `versions/<id>` containing `daily.json` and `risk.json`.
Publication changes this pointer atomically after both files validate. Private data
is never exported to `front/public` or committed to collection/snapshot Git branches.
The authenticated API reads the snapshot and applies user scope.
After publication, generated UUID snapshot directories older than 24 hours are removed,
except the newest three generations. The web worker and CLI serialize writes with a
private file lock. Queue ownership is also locked across API processes, with takeover
after an owning process exits. Interrupted work is reported and can be retried from
the web interface; queued jobs persist across restarts.

Historical `data/processed` observations are reused. The recovered ridership file
includes all 80 reviewed contracts. Old water CSV aliases are resolved through the
reviewed `data/billing/meter_match.csv`; new data carries its customer number directly.
Unknown aliases fail validation rather than being guessed. Calendar coverage is
regenerated for the available observations. Display labels come from the registry.

Model defaults run on CPU and use the current `back/ml/lightgbm` code. The final model
uses the validation model's best iteration. Residual center/scale and anomaly thresholds
are fixed from validation; later test observations cannot change earlier scores.
Bill baselines use only bills available before the observation. Historical exports lack
an exact issue date, so the first day after the ending billing month is the conservative
availability boundary; incomplete one-month buckets are excluded from this baseline.

A contract needs at least 90 training observations and 14 validation observations for
risk publication. New contracts still show observations; `manifest.withheld` records
why risk is unavailable. Existing train/validation date cutoffs are preserved. After
reviewing a newer evaluation period, pass `--train-end YYYY-MM-DD --valid-end YYYY-MM-DD`
to retrain with updated boundaries. Model configuration and result location can also
be selected with `python -m back.ml.lightgbm.main --config path.yaml --out-dir path`.

The optional, manually dispatched Actions workflow uses a trusted self-hosted runner and persistent
`APP_DATA_DIR` outside its checkout. Initialize its database and contract registry
first and configure repository secrets and storage variables. Scheduling belongs to the
web application so turning it off there also stops automatic Arisu collection. Source
code is checked out from `main`; observations and
snapshots remain in private persistent storage. There is no Git push or public artifact
upload. Concurrent refresh jobs share one Actions concurrency group and the collection
file lock. Do not point separate installations at the same database with different
data directories.

The web application's one-contract collector is `incremental.collect_meter`. It probes
daily readings only when daily collection is enabled, fills missing historical
months, and retries the recent three months. Contracts without observations start with the
latest twelve calendar months. Older empty months are retried after seven days; empty
results never prove that a customer number is invalid. The reviewed collection setting is preserved after collection. Public bill details refresh
recent charges, usage periods and separate water/groundwater readings. Missing source
fields do not erase stored details or user-entered addresses.
Failed bill windows are recorded for a subsequent retry even if older imported rows
already cover their months.

Application jobs can pass one authenticated `session` to reuse it for the entire batch;
the caller owns that session. Missing credentials, authentication failures, empty responses,
and partial success have separate results. All network checks are mocked in
`python -m unittest discover -s tests -p test_incremental.py`.

Web collection and `refresh` CLI writes share the private `.collection.lock` file lock.
Updated observations are published with existing risk results; model analysis still runs
separately. Snapshot cleanup runs only after successful publication and retains every
version from the last 24 hours plus at least the three latest versions.
