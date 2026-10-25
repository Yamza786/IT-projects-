module FraudAnomalyWorkbench

using DBInterface
using SQLite

export Transaction, Baseline, Score, train_baseline, score_transaction, save_scores!, list_scores, review_score!, export_csv, parse_csv

struct Transaction
    id::String
    amount_cents::Int64
    category::String
    hour_utc::Int
    new_device::Bool
    country_change::Bool
    function Transaction(id::AbstractString, amount_cents::Integer, category::AbstractString, hour_utc::Integer, new_device::Bool, country_change::Bool)
        1 <= ncodeunits(id) <= 64 || throw(ArgumentError("transaction id must contain 1–64 bytes"))
        occursin(r"^[A-Za-z0-9._-]+$", id) || throw(ArgumentError("transaction id contains unsupported characters"))
        1 <= amount_cents <= 100_000_000_000 || throw(ArgumentError("amount must be positive and within the limit"))
        1 <= ncodeunits(category) <= 64 || throw(ArgumentError("category must contain 1–64 bytes"))
        occursin(r"^[A-Za-z0-9._-]+$", category) || throw(ArgumentError("category contains unsupported characters"))
        0 <= hour_utc <= 23 || throw(ArgumentError("hour_utc must be 0–23"))
        new(String(id), Int64(amount_cents), String(category), Int(hour_utc), new_device, country_change)
    end
end

struct Baseline
    means::Dict{String,Float64}
    deviations::Dict{String,Float64}
    sample_counts::Dict{String,Int}
end

struct Score
    transaction::Transaction
    z_score::Float64
    flagged::Bool
    reasons::Vector{String}
end

function train_baseline(history::Vector{Transaction})
    isempty(history) && throw(ArgumentError("history must include at least one transaction"))
    amounts = Dict{String,Vector{Float64}}()
    for item in history
        push!(get!(amounts, item.category, Float64[]), Float64(item.amount_cents))
    end
    means = Dict{String,Float64}(); deviations = Dict{String,Float64}(); counts = Dict{String,Int}()
    for (category, values) in amounts
        means[category] = sum(values) / length(values)
        deviations[category] = length(values) > 1 ? sqrt(sum((value - means[category])^2 for value in values) / (length(values) - 1)) : 0.0
        counts[category] = length(values)
    end
    Baseline(means, deviations, counts)
end

function score_transaction(baseline::Baseline, item::Transaction; threshold::Float64=3.0)
    threshold > 0 || throw(ArgumentError("threshold must be positive"))
    haskey(baseline.means, item.category) || throw(ArgumentError("no training baseline for category $(item.category)"))
    mean = baseline.means[item.category]; deviation = baseline.deviations[item.category]
    raw = deviation == 0 ? (item.amount_cents == mean ? 0.0 : 20.0) : abs(item.amount_cents - mean) / deviation
    z = min(raw, 20.0)
    reasons = String[]
    z >= threshold && push!(reasons, "unusual_amount")
    item.new_device && push!(reasons, "new_device")
    item.country_change && push!(reasons, "country_change")
    Score(item, round(z; digits=2), !isempty(reasons), reasons)
end

function initialize(db::SQLite.DB)
    DBInterface.execute(db, "PRAGMA foreign_keys=ON")
    DBInterface.execute(db, "CREATE TABLE IF NOT EXISTS review_scores (
        transaction_id TEXT PRIMARY KEY CHECK(length(transaction_id) BETWEEN 1 AND 64),
        amount_cents INTEGER NOT NULL CHECK(amount_cents BETWEEN 1 AND 100000000000),
        category TEXT NOT NULL CHECK(length(category) BETWEEN 1 AND 64),
        hour_utc INTEGER NOT NULL CHECK(hour_utc BETWEEN 0 AND 23),
        z_score REAL NOT NULL CHECK(z_score BETWEEN 0 AND 20),
        flagged INTEGER NOT NULL CHECK(flagged IN (0,1)),
        reasons TEXT NOT NULL,
        review_state TEXT NOT NULL DEFAULT 'pending' CHECK(review_state IN ('pending','accepted','rejected')),
        scored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )")
end

function save_scores!(db::SQLite.DB, scores::Vector{Score})
    initialize(db)
    DBInterface.execute(db, "BEGIN IMMEDIATE")
    try
        for result in scores
            item = result.transaction
            reasons = join(result.reasons, ",")
            DBInterface.execute(db, "INSERT INTO review_scores(transaction_id,amount_cents,category,hour_utc,z_score,flagged,reasons) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(transaction_id) DO UPDATE SET amount_cents=excluded.amount_cents,category=excluded.category,hour_utc=excluded.hour_utc,z_score=excluded.z_score,flagged=excluded.flagged,reasons=excluded.reasons,review_state='pending',scored_at=CURRENT_TIMESTAMP",
                (item.id, item.amount_cents, item.category, item.hour_utc, result.z_score, result.flagged ? 1 : 0, reasons))
        end
        DBInterface.execute(db, "COMMIT")
    catch error
        DBInterface.execute(db, "ROLLBACK")
        rethrow()
    end
    length(scores)
end

function list_scores(db::SQLite.DB; flagged_only::Bool=false)
    initialize(db)
    sql = flagged_only ? "SELECT transaction_id,amount_cents,category,hour_utc,z_score,flagged,reasons,review_state FROM review_scores WHERE flagged=1 ORDER BY scored_at,transaction_id" : "SELECT transaction_id,amount_cents,category,hour_utc,z_score,flagged,reasons,review_state FROM review_scores ORDER BY scored_at,transaction_id"
    collect(DBInterface.execute(db, sql))
end

function review_score!(db::SQLite.DB, transaction_id::AbstractString, state::AbstractString)
    state in ("accepted", "rejected") || throw(ArgumentError("review state must be accepted or rejected"))
    DBInterface.execute(db, "UPDATE review_scores SET review_state=? WHERE transaction_id=? AND flagged=1", (state, transaction_id))
    first(collect(DBInterface.execute(db, "SELECT changes() AS changed"))).changed == 1 || throw(ArgumentError("flagged transaction does not exist"))
    state
end

function csv_cell(value)
    text = string(value)
    "\"" * replace(text, "\"" => "\"\"") * "\""
end

function export_csv(db::SQLite.DB, path::AbstractString)
    rows = list_scores(db)
    open(path, "w") do output
        println(output, "transaction_id,amount_cents,category,hour_utc,z_score,flagged,reasons,review_state")
        for row in rows
            values = (row.transaction_id, row.amount_cents, row.category, row.hour_utc, row.z_score, row.flagged, row.reasons, row.review_state)
            println(output, join(csv_cell.(values), ','))
        end
    end
    length(rows)
end

function parse_csv(path::AbstractString)
    isfile(path) || throw(ArgumentError("CSV must be an existing regular file"))
    filesize(path) <= 8 * 1024 * 1024 || throw(ArgumentError("CSV exceeds 8 MiB"))
    lines = readlines(path)
    isempty(lines) && throw(ArgumentError("CSV is empty"))
    expected = "transaction_id,amount_cents,category,hour_utc,new_device,country_change"
    strip(lines[1]) == expected || throw(ArgumentError("CSV header must exactly match the documented columns"))
    length(lines) <= 10_001 || throw(ArgumentError("CSV exceeds 10,000 rows"))
    result = Transaction[]
    seen = Set{String}()
    for (line_number, line) in enumerate(lines[2:end], 2)
        fields = split(chomp(line), ',')
        length(fields) == 6 || throw(ArgumentError("row $line_number must contain exactly six unquoted fields"))
        id, amount, category, hour, new_device, country_change = fields
        id in seen && throw(ArgumentError("duplicate transaction_id on row $line_number"))
        push!(seen, id)
        new_device in ("true", "false") || throw(ArgumentError("new_device must be true or false on row $line_number"))
        country_change in ("true", "false") || throw(ArgumentError("country_change must be true or false on row $line_number"))
        push!(result, Transaction(id, parse(Int64, amount), category, parse(Int, hour), new_device == "true", country_change == "true"))
    end
    isempty(result) && throw(ArgumentError("CSV must contain at least one transaction"))
    result
end

end
