package dev.portfolio.pocketledger

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first
import java.time.LocalDate

@RunWith(AndroidJUnit4::class)
class LedgerMigrationTest {
    @Test fun migratesLegacyBudgetKeyAndPreservesRows() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "migration-test.db"
        context.deleteDatabase(name)
        createVersionOneDatabase(context, name)
        val migrated = Room.databaseBuilder(context, LedgerDatabase::class.java, name)
            .addMigrations(MIGRATION_1_2)
            .allowMainThreadQueries()
            .build()
        try {
            assertEquals(2, migrated.openHelper.readableDatabase.version)
            val cursor = migrated.openHelper.readableDatabase.query("SELECT category,limitMinor,currency FROM budgets")
            try {
                assertTrue(cursor.moveToFirst())
                assertEquals("Food", cursor.getString(0))
                assertEquals(50000L, cursor.getLong(1))
                assertEquals("USD", cursor.getString(2))
            } finally {
                cursor.close()
            }
        } finally {
            migrated.close()
            context.deleteDatabase(name)
        }
    }

    @Test fun recurringRunsAreTransactionalAndDoNotDuplicate() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "recurring-test.db"
        context.deleteDatabase(name)
        val database = Room.databaseBuilder(context, LedgerDatabase::class.java, name)
            .addMigrations(MIGRATION_1_2)
            .allowMainThreadQueries()
            .build()
        try {
            val repository = LedgerRepository(database)
            val today = LocalDate.now()
            repository.addRecurring(2500, "USD", EntryKind.EXPENSE, "Transport", "monthly pass", RecurrenceFrequency.MONTHLY, today)
            assertEquals(1, repository.processDueRecurring(today))
            assertEquals(0, repository.processDueRecurring(today))
            val cursor = database.openHelper.readableDatabase.query("SELECT COUNT(*) FROM ledger_entries")
            try { assertTrue(cursor.moveToFirst()); assertEquals(1L, cursor.getLong(0)) } finally { cursor.close() }
            assertEquals(1, repository.monthlyReport(today.toString().substring(0, 7), "USD").first().size)
            assertTrue(repository.exportMonthCsv(today.toString().substring(0, 7), "USD").contains("monthly pass"))
        } finally {
            database.close()
            context.deleteDatabase(name)
        }
    }

    private fun createVersionOneDatabase(context: Context, name: String) {
        val path = context.getDatabasePath(name)
        path.parentFile?.mkdirs()
        val db = SQLiteDatabase.openOrCreateDatabase(path, null)
        db.execSQL("CREATE TABLE ledger_entries (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, amountMinor INTEGER NOT NULL, currency TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, memo TEXT NOT NULL, occurredOn TEXT NOT NULL, createdAtEpochMillis INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE budgets (month TEXT NOT NULL, category TEXT NOT NULL, limitMinor INTEGER NOT NULL, currency TEXT NOT NULL, PRIMARY KEY(month,category))")
        db.execSQL("INSERT INTO budgets(month,category,limitMinor,currency) VALUES ('2026-10','Food',50000,'USD')")
        db.version = 1
        db.close()
    }
}
