package dev.portfolio.pocketledger

import android.os.Bundle
import android.net.Uri
import android.content.Context
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.room.Room
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import java.math.BigDecimal

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val db = LedgerDatabaseProvider.get(applicationContext)
        val repository = LedgerRepository(db)
        setContent { MaterialTheme { LedgerScreen(repository) } }
    }
}

object LedgerDatabaseProvider {
    @Volatile private var instance: LedgerDatabase? = null

    fun get(context: Context): LedgerDatabase = instance ?: synchronized(this) {
        instance ?: Room.databaseBuilder(context.applicationContext, LedgerDatabase::class.java, "pocket-ledger.db")
            .addMigrations(MIGRATION_1_2)
            .build()
            .also { instance = it }
    }
}

@Composable
private fun LedgerScreen(repository: LedgerRepository) {
    val entries by repository.entries.collectAsState(initial = emptyList())
    val balance by repository.balance("USD").collectAsState(initial = 0L)
    var amount by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("") }
    var budgetLimit by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf(EntryKind.EXPENSE) }
    var frequency by remember { mutableStateOf(RecurrenceFrequency.MONTHLY) }
    var message by remember { mutableStateOf("") }
    var pendingCsv by remember { mutableStateOf<String?>(null) }
    val month = remember { YearMonth.now().toString() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val budgets by repository.budgetProgress(month, "USD").collectAsState(initial = emptyList())
    val totals by repository.monthlyReport(month, "USD").collectAsState(initial = emptyList())
    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri: Uri? ->
        val csv = pendingCsv
        pendingCsv = null
        if (uri != null && csv != null) scope.launch {
            runCatching {
                context.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(csv) }
                    ?: error("Could not open the selected export destination")
            }.onSuccess { message = "CSV export saved" }.onFailure { message = it.message ?: "Export failed" }
        }
    }
    LaunchedEffect(Unit) {
        runCatching { repository.processDueRecurring() }
            .onSuccess { count -> if (count > 0) message = "Processed recurring entries: $count occurrence(s)" }
            .onFailure { message = it.message ?: "Could not process recurring entries" }
    }
    Scaffold { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Pocket Ledger", style = MaterialTheme.typography.headlineMedium)
            Text("Balance: \$${money(balance)}")
            Text("$month report · Income ${money(totals.firstOrNull { it.kind == EntryKind.INCOME.name }?.amountMinor ?: 0)} · Expenses ${money(totals.firstOrNull { it.kind == EntryKind.EXPENSE.name }?.amountMinor ?: 0)}")
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount (USD)") }, singleLine = true)
            OutlinedTextField(category, { category = it }, label = { Text("Category") }, singleLine = true)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EntryKind.entries.forEach { option ->
                    FilterChip(selected = kind == option, onClick = { kind = option }, label = { Text(option.name.lowercase().replaceFirstChar { it.uppercase() }) })
                }
            }
            Button(onClick = {
                val cents = MoneyInput.parseMinorUnits(amount)
                if (cents == null) message = "Enter a valid positive amount with up to two decimal places"
                else scope.launch {
                    runCatching { repository.record(cents, "USD", kind, category, "", LocalDate.now()) }
                        .onSuccess { amount = ""; message = "${kind.name.lowercase().replaceFirstChar { it.uppercase() }} saved" }
                        .onFailure { message = it.message ?: "Could not save expense" }
                }
            }) { Text("Add ${kind.name.lowercase()}") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                RecurrenceFrequency.entries.forEach { option ->
                    FilterChip(selected = frequency == option, onClick = { frequency = option }, label = { Text(option.name.lowercase().replaceFirstChar { it.uppercase() }) })
                }
            }
            Button(onClick = {
                val minor = MoneyInput.parseMinorUnits(amount)
                if (minor == null) message = "Enter a valid positive amount with up to two decimal places"
                else scope.launch {
                    runCatching {
                        repository.addRecurring(minor, "USD", kind, category, "", frequency, LocalDate.now())
                        repository.processDueRecurring()
                    }.onSuccess { amount = ""; message = "Recurring entry saved and first occurrence recorded" }
                        .onFailure { message = it.message ?: "Could not save recurring entry" }
                }
            }) { Text("Schedule recurring entry") }
            Text("Monthly budgets", style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(budgetLimit, { budgetLimit = it }, label = { Text("Monthly limit (USD)") }, singleLine = true)
            Button(onClick = {
                val minor = MoneyInput.parseMinorUnits(budgetLimit)
                if (minor == null || category.isBlank()) message = "Enter a valid limit and category"
                else scope.launch {
                    runCatching { repository.setBudget(month, category, minor, "USD") }
                        .onSuccess { budgetLimit = ""; message = "Budget saved" }
                        .onFailure { message = it.message ?: "Could not save budget" }
                }
            }) { Text("Save category budget") }
            budgets.forEach { budget -> Text("${budget.category}: spent ${money(budget.spentMinor)} of ${money(budget.limitMinor)}") }
            Button(onClick = {
                scope.launch {
                    runCatching { repository.exportMonthCsv(month, "USD") }
                        .onSuccess { pendingCsv = it; exportLauncher.launch("pocket-ledger-$month.csv") }
                        .onFailure { message = it.message ?: "Could not prepare CSV export" }
                }
            }) { Text("Export $month CSV") }
            Text(message)
            Text("Recent entries", style = MaterialTheme.typography.titleLarge)
            entries.take(100).forEach { entry -> Text("${entry.occurredOn} · ${entry.category} · ${entry.kind} · ${entry.currency} ${money(entry.amountMinor)}", Modifier.padding(vertical = 5.dp)) }
        }
    }
}

private fun money(minor: Long): String {
    val sign = if (minor < 0) "-" else ""
    return sign + BigDecimal.valueOf(minor).abs().movePointLeft(2).toPlainString()
}
