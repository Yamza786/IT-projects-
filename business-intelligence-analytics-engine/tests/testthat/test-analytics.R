make_rows <- function() {
  data.frame(
    transaction_id = c("txn-a", "txn-b"),
    booked_on = c("2026-03-01", "2026-03-02"),
    amount_cents = c("5000", "1200"),
    direction = c("income", "expense"),
    category = c("contract", "food"),
    source_id = c("fixture", "fixture"),
    stringsAsFactors = FALSE
  )
}

testthat::test_that("import is transactional, repeatable, and aggregates deterministically", {
  path <- tempfile(fileext = ".sqlite")
  connection <- connect_warehouse(path)
  on.exit({ DBI::dbDisconnect(connection); unlink(c(path, paste0(path, "-wal"), paste0(path, "-shm"))) }, add = TRUE)

  second_connection <- connect_warehouse(path)
  DBI::dbDisconnect(second_connection)

  rows <- make_rows()
  testthat::expect_equal(import_transactions(connection, rows), list(inserted = 2L, unchanged = 0L))
  testthat::expect_equal(import_transactions(connection, rows), list(inserted = 0L, unchanged = 2L))
  report <- monthly_report(connection, "2026-03")
  testthat::expect_equal(sum(report$amount_cents), 6200)
  testthat::expect_equal(sum(report$transaction_count), 2L)
  testthat::expect_equal(quality_summary(connection)$unique_ids, 2L)
})

testthat::test_that("invalid imports and conflicting replay roll back without partial writes", {
  path <- tempfile(fileext = ".sqlite")
  connection <- connect_warehouse(path)
  on.exit({ DBI::dbDisconnect(connection); unlink(c(path, paste0(path, "-wal"), paste0(path, "-shm"))) }, add = TRUE)

  rows <- make_rows()
  invalid <- rows
  invalid$amount_cents[[2]] <- "0"
  testthat::expect_error(import_transactions(connection, invalid), "amount_cents")
  testthat::expect_equal(DBI::dbGetQuery(connection, "SELECT COUNT(*) AS n FROM ledger_transactions")$n, 0L)

  import_transactions(connection, rows)
  conflict <- rows
  conflict$category[[1]] <- "changed category"
  testthat::expect_error(import_transactions(connection, conflict), "already exists with different data")
  testthat::expect_equal(DBI::dbGetQuery(connection, "SELECT COUNT(*) AS n FROM ledger_transactions")$n, 2L)
})

testthat::test_that("CSV import checks headers and calendar dates", {
  rows <- make_rows()
  testthat::expect_silent(validate_import(rows))
  malformed <- rows
  malformed$booked_on[[1]] <- "2026-02-30"
  testthat::expect_error(validate_import(malformed), "valid ISO dates")
  reordered <- rows[, rev(names(rows))]
  testthat::expect_error(validate_import(reordered), "documented columns")
  connection <- DBI::dbConnect(RSQLite::SQLite(), ":memory:")
  on.exit(DBI::dbDisconnect(connection), add = TRUE)
  testthat::expect_error(monthly_report(connection, "2026-13"), "YYYY-MM")
})
