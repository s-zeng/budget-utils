import "time"

budgetName:          string
personalAccessToken: string
categoryGroupWatchList: {[string]: string}
resolution_date: null | time.Time
showAllRows:     bool
outputFormat: "polars_print" | "csv_print" | {csv_output: string} | {visual_output: string}
