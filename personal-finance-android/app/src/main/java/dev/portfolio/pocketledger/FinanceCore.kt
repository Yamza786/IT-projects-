package dev.portfolio.pocketledger

import java.math.BigDecimal
import java.time.LocalDate
import java.time.YearMonth

enum class EntryKind { INCOME, EXPENSE }
enum class RecurrenceFrequency { WEEKLY, MONTHLY }

object MoneyInput {
    private const val MAX_MINOR_UNITS = 1_000_000_000_000L
    private val decimalPattern = Regex("[0-9]+(?:\\.[0-9]{1,2})?")

    fun parseMinorUnits(value: String): Long? {
        val normalized = value.trim()
        if (!decimalPattern.matches(normalized)) return null
        return try {
            BigDecimal(normalized).movePointRight(2).longValueExact().takeIf { it in 1L..MAX_MINOR_UNITS }
        } catch (_: NumberFormatException) {
            null
        } catch (_: ArithmeticException) {
            null
        }
    }
}

object RecurrenceSchedule {
    fun next(date: LocalDate, frequency: RecurrenceFrequency, anchorDay: Int = date.dayOfMonth): LocalDate = when (frequency) {
        RecurrenceFrequency.WEEKLY -> date.plusWeeks(1)
        RecurrenceFrequency.MONTHLY -> {
            val month = YearMonth.from(date).plusMonths(1)
            month.atDay(anchorDay.coerceIn(1, month.lengthOfMonth()))
        }
    }
}

object CsvSafety {
    fun cell(value: String): String {
        val first = value.dropWhile { it.isWhitespace() }.firstOrNull()
        val dangerous = first == '=' || first == '+' || first == '-' || first == '@' || first == '\t' || first == '\r'
        val safe = if (dangerous) "'$value" else value
        return "\"${safe.replace("\"", "\"\"")}\""
    }
}
