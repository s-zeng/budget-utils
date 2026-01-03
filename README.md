## budget-utils

Weekly budget reporting helper for YNAB. It pulls categories and transactions,
calculates weekly spend against planned amounts, and outputs either a printed
table, CSV, or a styled HTML report.

Please see the files in tests/golden/ to see sample outputs

## Requirements

- Python 3.14+
- A YNAB personal access token

## Quick start

1. Create `config.json` (see config section below). If you use the CUE files,
   you can run `make config.json` after filling in `secrets.cue`.
2. Run the CLI:

```bash
uv run budget-utils
```

If you prefer installing locally:

```bash
pip install -e .
budget-utils
```

## Configuration

`config.json` is required at the repository root.

If you prefer CUE, edit `secrets.cue` (for the token, budget name, and
categories) and `config.cue` (for other settings), then run:

```bash
make config.json
```

This keeps secrets out of `config.cue` and lets you validate the shape against
`configSchema.cue` before exporting.

```json
{
  "budgetName": "My budget",
  "personalAccessToken": "ynab-token",
  "categoryGroupWatchList": {
    "Everyday Spend": "#f6f3ea",
    "Eating Out": "#f6ead7"
  },
  "resolution_date": "2024-08-15",
  "showAllRows": false,
  "outputFormat": "polars_print"
}
```

Field notes:

- `budgetName`: YNAB budget name to report on.
- `personalAccessToken`: YNAB access token (keep this private).
- `categoryGroupWatchList`: map of category group name to a hex color for reports.
- `resolution_date`: optional ISO date (`YYYY-MM-DD`); defaults to today if null.
- `showAllRows`: show rows with zero spend when true.
- `outputFormat`: one of:
  - `"polars_print"`: pretty-printed tables in stdout.
  - `"csv_print"`: CSV tables in stdout.
  - `{ "csv_output": "report.csv" }`: write CSVs to disk.
  - `{ "visual_output": "report.html" }`: write a styled HTML report.

## Output files

When writing CSVs, a second file named `*_category_group_totals.csv` is created
next to the primary CSV. HTML output is a single file.

## Development

```bash
ruff format
make verify
```
