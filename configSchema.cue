import "time"

budgetName:             string
personalAccessToken:    string
categoryGroupWatchlist: list[string]
resolution_date:        null | time.Time
showAllRows:            bool
outputFormat:           "polars_print" | "csv_print" | {csv_output: string}
