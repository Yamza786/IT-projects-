database_path <- function() {
  value <- Sys.getenv("BI_DATABASE", unset = "./build/analytics.sqlite")
  if (!nzchar(value) || identical(value, ":memory:")) stop("database path must be a non-empty file path", call. = FALSE)
  value
}

connect_warehouse <- function(path = database_path()) {
  if (!nzchar(path) || identical(path, ":memory:")) stop("use a file-backed database path", call. = FALSE)
  directory <- dirname(path)
  if (!dir.exists(directory)) dir.create(directory, recursive = TRUE, mode = "0700")
  if (file.exists(path) && dir.exists(path)) stop("database path must be a regular file", call. = FALSE)
  connection <- DBI::dbConnect(RSQLite::SQLite(), path)
  tryCatch({
    DBI::dbExecute(connection, "PRAGMA foreign_keys = ON")
    DBI::dbGetQuery(connection, "PRAGMA journal_mode = WAL")
    if (.Platform$OS.type != "windows") Sys.chmod(path, mode = "0600")
    apply_migrations(connection)
    connection
  }, error = function(error) {
    DBI::dbDisconnect(connection)
    stop(error)
  })
}

apply_migrations <- function(connection) {
  root <- normalizePath(getwd(), mustWork = TRUE)
  while (!dir.exists(file.path(root, "sql", "migrations"))) {
    parent <- dirname(root)
    if (identical(parent, root)) stop("cannot locate SQL migrations from the working directory", call. = FALSE)
    root <- parent
  }
  migration_dir <- file.path(root, "sql", "migrations")
  files <- sort(list.files(migration_dir, pattern = "^[0-9]+_.*\\.sql$", full.names = TRUE))
  if (length(files) == 0L) stop("no SQL migrations found", call. = FALSE)
  DBI::dbExecute(connection, "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
  DBI::dbBegin(connection)
  tryCatch({
    for (file in files) {
      version <- basename(file)
      checksum <- unname(tools::md5sum(file))
      applied <- DBI::dbGetQuery(connection, "SELECT checksum FROM schema_migrations WHERE version = ?", params = list(version))
      if (nrow(applied) > 0L) {
        if (!identical(applied$checksum[[1]], checksum)) stop(sprintf("applied migration %s was modified", version), call. = FALSE)
      } else {
        DBI::dbExecute(connection, paste(readLines(file, warn = FALSE), collapse = "\n"))
        DBI::dbExecute(connection, "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)", params = list(version, checksum))
      }
    }
    DBI::dbCommit(connection)
  }, error = function(error) {
    DBI::dbRollback(connection)
    stop(error)
  })
}

validate_import <- function(data) {
  required <- c("transaction_id", "booked_on", "amount_cents", "direction", "category", "source_id")
  if (!identical(names(data), required)) stop("CSV must contain exactly the documented columns in the documented order", call. = FALSE)
  if (nrow(data) == 0L) stop("CSV must contain at least one transaction", call. = FALSE)
  if (anyNA(data) || any(vapply(data, function(column) any(!nzchar(trimws(column))), logical(1)))) stop("CSV fields cannot be empty", call. = FALSE)
  if (any(nchar(data$transaction_id, type = "bytes") > 64L) || anyDuplicated(data$transaction_id)) stop("transaction IDs must be unique and at most 64 bytes", call. = FALSE)
  valid_date <- grepl("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", data$booked_on)
  parsed_date <- as.Date(data$booked_on, format = "%Y-%m-%d")
  valid_date <- valid_date & !is.na(parsed_date) & format(parsed_date, "%Y-%m-%d") == data$booked_on
  if (any(!valid_date)) stop("booked_on must contain valid ISO dates (YYYY-MM-DD)", call. = FALSE)
  if (any(!grepl("^[1-9][0-9]{0,11}$", data$amount_cents))) stop("amount_cents must be a positive integer no greater than 100000000000", call. = FALSE)
  if (any(!data$direction %in% c("income", "expense"))) stop("direction must be income or expense", call. = FALSE)
  if (any(nchar(data$category, type = "bytes") > 80L) || any(nchar(data$source_id, type = "bytes") > 96L)) stop("category/source_id exceeds its allowed length", call. = FALSE)
  invisible(data)
}

read_transactions <- function(path) {
  if (!file.exists(path) || dir.exists(path)) stop("CSV path must be an existing regular file", call. = FALSE)
  field_counts <- utils::count.fields(path, sep = ",", quote = "\"", comment.char = "")
  if (anyNA(field_counts) || any(field_counts != 6L)) stop("CSV contains a malformed row or unexpected number of fields", call. = FALSE)
  data <- utils::read.csv(path, colClasses = "character", stringsAsFactors = FALSE, check.names = FALSE, na.strings = character(), row.names = NULL)
  validate_import(data)
  data
}

import_transactions <- function(connection, data) {
  validate_import(data)
  DBI::dbBegin(connection)
  inserted <- 0L
  unchanged <- 0L
  tryCatch({
    for (index in seq_len(nrow(data))) {
      row <- data[index, , drop = FALSE]
      existing <- DBI::dbGetQuery(connection, "SELECT transaction_id, booked_on, amount_cents, direction, category, source_id FROM ledger_transactions WHERE transaction_id = ?", params = list(row$transaction_id[[1]]))
      if (nrow(existing) > 0L) {
        same <- all(vapply(names(row), function(name) identical(as.character(existing[[name]][[1]]), as.character(row[[name]][[1]])), logical(1)))
        if (!same) stop(sprintf("transaction ID %s already exists with different data", row$transaction_id[[1]]), call. = FALSE)
        unchanged <- unchanged + 1L
      } else {
        changed <- DBI::dbExecute(connection, "INSERT INTO ledger_transactions (transaction_id, booked_on, amount_cents, direction, category, source_id) VALUES (?, ?, ?, ?, ?, ?)", params = list(row$transaction_id[[1]], row$booked_on[[1]], as.numeric(row$amount_cents[[1]]), row$direction[[1]], row$category[[1]], row$source_id[[1]]))
        if (changed != 1L) stop("transaction insert did not affect exactly one row", call. = FALSE)
        inserted <- inserted + 1L
      }
    }
    DBI::dbCommit(connection)
    list(inserted = inserted, unchanged = unchanged)
  }, error = function(error) {
    DBI::dbRollback(connection)
    stop(error)
  })
}

monthly_report <- function(connection, month = NULL) {
  if (!is.null(month) && !grepl("^[0-9]{4}-(0[1-9]|1[0-2])$", month)) stop("month must use YYYY-MM", call. = FALSE)
  if (is.null(month)) {
    query <- "SELECT month, category, direction, transaction_count, amount_cents FROM monthly_category_summary ORDER BY month, category, direction"
    DBI::dbGetQuery(connection, query)
  } else {
    query <- "SELECT month, category, direction, transaction_count, amount_cents FROM monthly_category_summary WHERE month = ? ORDER BY category, direction"
    DBI::dbGetQuery(connection, query, params = list(month))
  }
}

quality_summary <- function(connection) {
  DBI::dbGetQuery(connection, "SELECT COUNT(*) AS transaction_count, COUNT(DISTINCT transaction_id) AS unique_ids, MIN(booked_on) AS first_date, MAX(booked_on) AS last_date FROM ledger_transactions")
}
