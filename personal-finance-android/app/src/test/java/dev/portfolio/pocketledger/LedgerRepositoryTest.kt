package dev.portfolio.pocketledger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class LedgerRepositoryTest {
    @Test fun rejectsZeroAndNegativeAmounts() {
        assertNull(MoneyInput.parseMinorUnits("0"))
        assertNull(MoneyInput.parseMinorUnits("-2.00"))
    }
    @Test fun rejectsFractionalMinorUnitAndOverflow() {
        assertNull(MoneyInput.parseMinorUnits("1.001"))
        assertNull(MoneyInput.parseMinorUnits("999999999999999999999999999"))
        assertNull(MoneyInput.parseMinorUnits("1e2"))
    }
    @Test fun parsesDecimalIntoExactMinorUnits() { assertEquals(1250L, MoneyInput.parseMinorUnits("12.50")) }
    @Test fun monthlyScheduleKeepsMonthEndAnchor() {
        assertEquals(LocalDate.parse("2025-02-28"), RecurrenceSchedule.next(LocalDate.parse("2025-01-31"), RecurrenceFrequency.MONTHLY, 31))
        assertEquals(LocalDate.parse("2025-03-31"), RecurrenceSchedule.next(LocalDate.parse("2025-02-28"), RecurrenceFrequency.MONTHLY, 31))
    }
    @Test fun weeklyScheduleAdvancesSevenDays() {
        assertEquals(LocalDate.parse("2025-01-08"), RecurrenceSchedule.next(LocalDate.parse("2025-01-01"), RecurrenceFrequency.WEEKLY))
    }
    @Test fun csvEscapesQuotesAndNeutralizesSpreadsheetFormulas() {
        assertEquals("\"'=SUM(A1:A2)\"", CsvSafety.cell("=SUM(A1:A2)"))
        assertEquals("\"a\"\"b\"", CsvSafety.cell("a\"b"))
        assertTrue(CsvSafety.cell("normal text").startsWith("\"normal"))
    }
}
