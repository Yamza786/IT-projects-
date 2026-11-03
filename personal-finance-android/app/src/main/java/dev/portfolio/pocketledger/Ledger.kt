package dev.portfolio.pocketledger

import androidx.room.*
import androidx.room.migration.Migration
import kotlinx.coroutines.flow.Flow
import androidx.room.withTransaction
import java.time.LocalDate

@Entity(tableName = "ledger_entries")
data class LedgerEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val amountMinor: Long,
    val currency: String,
    val kind: String,
    val category: String,
    val memo: String,
    val occurredOn: String,
    val createdAtEpochMillis: Long = System.currentTimeMillis()
)

@Entity(tableName = "budgets", primaryKeys = ["month", "category", "currency"])
data class Budget(val month: String, val category: String, val limitMinor: Long, val currency: String)

data class BudgetProgress(val category: String, val currency: String, val limitMinor: Long, val spentMinor: Long)
data class KindTotal(val kind: String, val currency: String, val amountMinor: Long)

@Entity(tableName = "recurring_rules")
data class RecurringRule(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val amountMinor: Long,
    val currency: String,
    val kind: String,
    val category: String,
    val memo: String,
    val frequency: String,
    val anchorDay: Int,
    val nextRunOn: String,
    val active: Boolean = true
)

@Entity(tableName = "recurrence_receipts", primaryKeys = ["ruleId", "scheduledFor"], indices = [Index(value = ["ruleId"])], foreignKeys = [ForeignKey(entity = RecurringRule::class, parentColumns = ["id"], childColumns = ["ruleId"], onDelete = ForeignKey.CASCADE)])
data class RecurrenceReceipt(val ruleId: Long, val scheduledFor: String, val ledgerEntryId: Long)

@Dao
interface LedgerDao {
    @Insert suspend fun insert(entry: LedgerEntry): Long
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun saveBudget(budget: Budget)
    @Insert suspend fun insertRecurring(rule: RecurringRule): Long
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun insertReceipt(receipt: RecurrenceReceipt): Long
    @Insert suspend fun insertEntry(entry: LedgerEntry): Long
    @androidx.room.Update suspend fun updateReceipt(receipt: RecurrenceReceipt)
    @androidx.room.Update suspend fun updateRecurring(rule: RecurringRule)
    @Query("SELECT * FROM ledger_entries ORDER BY occurredOn DESC, id DESC") fun entries(): Flow<List<LedgerEntry>>
    @Query("SELECT COALESCE(SUM(CASE WHEN kind='INCOME' THEN amountMinor ELSE -amountMinor END),0) FROM ledger_entries WHERE currency=:currency") fun balance(currency: String): Flow<Long>
    @Query("SELECT COALESCE(SUM(amountMinor),0) FROM ledger_entries WHERE kind='EXPENSE' AND category=:category AND substr(occurredOn,1,7)=:month AND currency=:currency") fun spent(category: String, month: String, currency: String): Flow<Long>
    @Query("SELECT * FROM budgets WHERE month=:month AND currency=:currency ORDER BY category") fun budgets(month: String, currency: String): Flow<List<Budget>>
    @Query("SELECT b.category AS category, b.currency AS currency, b.limitMinor AS limitMinor, COALESCE(SUM(e.amountMinor),0) AS spentMinor FROM budgets b LEFT JOIN ledger_entries e ON e.category=b.category AND e.currency=b.currency AND e.kind='EXPENSE' AND substr(e.occurredOn,1,7)=b.month WHERE b.month=:month AND b.currency=:currency GROUP BY b.month,b.category,b.currency,b.limitMinor ORDER BY b.category") fun budgetProgress(month: String, currency: String): Flow<List<BudgetProgress>>
    @Query("SELECT * FROM recurring_rules WHERE active=1 AND nextRunOn<=:today ORDER BY nextRunOn,id") suspend fun dueRecurring(today: String): List<RecurringRule>
    @Query("SELECT kind,currency,SUM(amountMinor) AS amountMinor FROM ledger_entries WHERE occurredOn BETWEEN :from AND :to AND currency=:currency GROUP BY kind,currency") fun totalsBetween(from: String, to: String, currency: String): Flow<List<KindTotal>>
    @Query("SELECT * FROM ledger_entries WHERE occurredOn BETWEEN :from AND :to ORDER BY occurredOn") suspend fun entriesBetween(from: String, to: String): List<LedgerEntry>
}

@Database(entities = [LedgerEntry::class, Budget::class, RecurringRule::class, RecurrenceReceipt::class], version = 2, exportSchema = true)
abstract class LedgerDatabase : RoomDatabase() { abstract fun ledgerDao(): LedgerDao }

val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(database: androidx.sqlite.db.SupportSQLiteDatabase) {
        database.execSQL("ALTER TABLE budgets RENAME TO budgets_legacy")
        database.execSQL("CREATE TABLE budgets (month TEXT NOT NULL, category TEXT NOT NULL, limitMinor INTEGER NOT NULL, currency TEXT NOT NULL, PRIMARY KEY(month,category,currency))")
        database.execSQL("INSERT INTO budgets(month,category,limitMinor,currency) SELECT month,category,limitMinor,currency FROM budgets_legacy")
        database.execSQL("DROP TABLE budgets_legacy")
        database.execSQL("CREATE TABLE IF NOT EXISTS recurring_rules (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, amountMinor INTEGER NOT NULL, currency TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, memo TEXT NOT NULL, frequency TEXT NOT NULL, anchorDay INTEGER NOT NULL, nextRunOn TEXT NOT NULL, active INTEGER NOT NULL)")
        database.execSQL("CREATE TABLE IF NOT EXISTS recurrence_receipts (ruleId INTEGER NOT NULL, scheduledFor TEXT NOT NULL, ledgerEntryId INTEGER NOT NULL, PRIMARY KEY(ruleId, scheduledFor), FOREIGN KEY(ruleId) REFERENCES recurring_rules(id) ON UPDATE NO ACTION ON DELETE CASCADE)")
        database.execSQL("CREATE INDEX IF NOT EXISTS index_recurrence_receipts_ruleId ON recurrence_receipts(ruleId)")
    }
}

class LedgerRepository(private val database: LedgerDatabase) {
    private val dao = database.ledgerDao()
    val entries = dao.entries()
    fun balance(currency: String) = dao.balance(currency)
    fun budgets(month: String, currency: String) = dao.budgets(month, currency)
    fun budgetProgress(month: String, currency: String) = dao.budgetProgress(month, currency)

    suspend fun record(amountMinor: Long, currency: String, kind: EntryKind, category: String, memo: String, date: LocalDate = LocalDate.now()): Long {
        require(amountMinor in 1..1_000_000_000_000L) { "Amount must be positive and bounded" }
        require(currency.matches(Regex("[A-Z]{3}"))) { "Currency must be a three-letter uppercase ISO code" }
        require(category.isNotBlank() && category.length <= 60) { "Category is required and must be at most 60 characters" }
        require(memo.length <= 240) { "Memo must be at most 240 characters" }
        return dao.insert(LedgerEntry(amountMinor = amountMinor, currency = currency, kind = kind.name, category = category.trim(), memo = memo.trim(), occurredOn = date.toString()))
    }

    suspend fun setBudget(month: String, category: String, limitMinor: Long, currency: String) {
        require(month.matches(Regex("\\d{4}-(0[1-9]|1[0-2])"))) { "Month must use YYYY-MM" }
        require(category.isNotBlank() && category.length <= 60)
        require(limitMinor in 0..1_000_000_000_000L)
        require(currency.matches(Regex("[A-Z]{3}")))
        dao.saveBudget(Budget(month, category.trim(), limitMinor, currency))
    }

    suspend fun addRecurring(amountMinor: Long, currency: String, kind: EntryKind, category: String, memo: String, frequency: RecurrenceFrequency, firstRun: LocalDate): Long {
        require(amountMinor in 1..1_000_000_000_000L) { "Amount must be positive and bounded" }
        require(currency.matches(Regex("[A-Z]{3}"))) { "Currency must be a three-letter uppercase ISO code" }
        require(category.isNotBlank() && category.length <= 60) { "Category is required and must be at most 60 characters" }
        require(memo.length <= 240) { "Memo must be at most 240 characters" }
        require(!firstRun.isBefore(LocalDate.now().minusDays(1))) { "First run cannot be in the past" }
        return dao.insertRecurring(RecurringRule(amountMinor = amountMinor, currency = currency, kind = kind.name, category = category.trim(), memo = memo.trim(), frequency = frequency.name, anchorDay = firstRun.dayOfMonth, nextRunOn = firstRun.toString()))
    }

    suspend fun processDueRecurring(today: LocalDate = LocalDate.now()): Int = database.withTransaction {
        var created = 0
        for (original in dao.dueRecurring(today.toString())) {
            var rule = original
            var periods = 0
            while (LocalDate.parse(rule.nextRunOn) <= today && periods < 520) {
                val scheduled = LocalDate.parse(rule.nextRunOn)
                val receiptId = dao.insertReceipt(RecurrenceReceipt(rule.id, scheduled.toString(), 0))
                if (receiptId != -1L) {
                    val entryId = dao.insertEntry(LedgerEntry(amountMinor = rule.amountMinor, currency = rule.currency, kind = rule.kind, category = rule.category, memo = rule.memo, occurredOn = scheduled.toString()))
                    // The occurrence key is the idempotency guard; ledgerEntryId is informational.
                    dao.updateReceipt(RecurrenceReceipt(rule.id, scheduled.toString(), entryId))
                    created++
                }
                rule = rule.copy(nextRunOn = RecurrenceSchedule.next(scheduled, RecurrenceFrequency.valueOf(rule.frequency), rule.anchorDay).toString())
                periods++
            }
            check(periods < 520 || LocalDate.parse(rule.nextRunOn) > today) { "Recurring catch-up exceeds the safe limit" }
            dao.updateRecurring(rule)
        }
        created
    }

    fun monthlyReport(month: String, currency: String): Flow<List<KindTotal>> {
        require(month.matches(Regex("\\d{4}-(0[1-9]|1[0-2])"))) { "Month must use YYYY-MM" }
        require(currency.matches(Regex("[A-Z]{3}")))
        val first = LocalDate.parse("$month-01")
        return dao.totalsBetween(first.toString(), first.withDayOfMonth(first.lengthOfMonth()).toString(), currency)
    }

    suspend fun exportMonthCsv(month: String, currency: String): String {
        require(month.matches(Regex("\\d{4}-(0[1-9]|1[0-2])"))) { "Month must use YYYY-MM" }
        require(currency.matches(Regex("[A-Z]{3}"))) { "Currency must be a three-letter uppercase ISO code" }
        val first = LocalDate.parse("$month-01")
        val entries = dao.entriesBetween(first.toString(), first.withDayOfMonth(first.lengthOfMonth()).toString()).filter { it.currency == currency }
        return buildString {
            appendLine("date,kind,category,amount_minor,currency,memo")
            entries.forEach { entry ->
                append(CsvSafety.cell(entry.occurredOn)).append(',')
                append(CsvSafety.cell(entry.kind)).append(',')
                append(CsvSafety.cell(entry.category)).append(',')
                append(entry.amountMinor).append(',')
                append(CsvSafety.cell(entry.currency)).append(',')
                append(CsvSafety.cell(entry.memo)).appendLine()
            }
        }
    }
}
