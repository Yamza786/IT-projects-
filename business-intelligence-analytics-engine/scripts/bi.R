source(file.path("R", "analytics.R"))

`%||%` <- function(value, fallback) if (is.null(value)) fallback else value

fail <- function(text) {
  base::message("error: ", gsub("[\r\n]+", " ", text))
  quit(status = 1L)
}

run <- function(arguments) {
  if (length(arguments) < 1L) fail("usage: Rscript scripts/bi.R init|import|report|quality [--db PATH] [--csv PATH] [--month YYYY-MM]")
  action <- arguments[[1]]
  options <- arguments[-1]
  if (length(options) %% 2L != 0L) fail("options must be supplied as --name value pairs")
  settings <- list()
  if (length(options) > 0L) {
    positions <- seq.int(1L, length(options), by = 2L)
    keys <- options[positions]
    values <- options[positions + 1L]
    if (any(!grepl("^--[a-z-]+$", keys))) fail("options must use --name syntax")
    setting_names <- sub("^--", "", keys)
    if (anyDuplicated(setting_names)) fail("each option can be supplied only once")
    settings <- as.list(stats::setNames(values, setting_names))
  }
  unknown <- setdiff(names(settings), c("db", "csv", "month"))
  if (length(unknown) > 0L) fail("unknown option")

  connection <- tryCatch(connect_warehouse(settings[["db"]] %||% database_path()), error = function(error) fail(conditionMessage(error)))
  on.exit(DBI::dbDisconnect(connection), add = TRUE)

  if (identical(action, "init")) {
    cat("{\"event\":\"warehouse_ready\"}\n")
  } else if (identical(action, "import")) {
    csv_path <- settings[["csv"]]
    if (is.null(csv_path)) fail("import requires --csv PATH")
    result <- tryCatch(import_transactions(connection, read_transactions(csv_path)), error = function(error) fail(conditionMessage(error)))
    cat(sprintf("{\"event\":\"import_complete\",\"inserted\":%d,\"unchanged\":%d}\n", result$inserted, result$unchanged))
  } else if (identical(action, "report")) {
    report <- tryCatch(monthly_report(connection, settings[["month"]]), error = function(error) fail(conditionMessage(error)))
    utils::write.csv(report, file = stdout(), row.names = FALSE, na = "")
  } else if (identical(action, "quality")) {
    utils::write.csv(quality_summary(connection), file = stdout(), row.names = FALSE, na = "")
  } else {
    fail("unknown action; use init, import, report, or quality")
  }
}

tryCatch(run(commandArgs(trailingOnly = TRUE)), error = function(error) fail(conditionMessage(error)))
