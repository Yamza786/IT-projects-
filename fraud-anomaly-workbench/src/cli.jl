using FraudAnomalyWorkbench
using SQLite

function demo()
    history = [
        Transaction("h-1", 1200, "groceries", 12, false, false),
        Transaction("h-2", 1450, "groceries", 13, false, false),
        Transaction("h-3", 1100, "groceries", 9, false, false),
        Transaction("h-4", 1350, "groceries", 18, false, false),
    ]
    observations = [
        Transaction("tx-101", 1290, "groceries", 14, false, false),
        Transaction("tx-102", 24000, "groceries", 3, true, true),
    ]
    history, observations
end

function main(args)
    if !isempty(args) && args[1] == "--review"
        length(args) == 4 || (println(stderr, "Usage: julia --project=. src/cli.jl --review ID accepted|rejected DATABASE_PATH"); return 2)
        db = SQLite.DB(args[4])
        try
            println(review_score!(db, args[2], args[3]))
        finally
            close(db)
        end
        return 0
    elseif !isempty(args) && args[1] == "--export"
        length(args) == 3 || (println(stderr, "Usage: julia --project=. src/cli.jl --export OUTPUT.csv DATABASE_PATH"); return 2)
        db = SQLite.DB(args[3])
        try
            println("exported_rows=$(export_csv(db, args[2]))")
        finally
            close(db)
        end
        return 0
    elseif length(args) > 1
        println(stderr, "Usage: julia --project=. src/cli.jl [DATABASE_PATH] | --review ID accepted|rejected DATABASE_PATH | --export OUTPUT.csv DATABASE_PATH")
        return 2
    end
    database = isempty(args) ? joinpath("data", "fraud-workbench.sqlite") : args[1]
    mkpath(dirname(abspath(database)))
    history, observations = demo()
    baseline = train_baseline(history)
    scores = [score_transaction(baseline, item) for item in observations]
    db = SQLite.DB(database)
    try
        save_scores!(db, scores)
        for score in list_scores(db)
            println("transaction=$(score.transaction_id) amount_cents=$(score.amount_cents) category=$(score.category) z=$(score.z_score) flagged=$(score.flagged) reasons=$(score.reasons) review=$(score.review_state)")
        end
    finally
        close(db)
    end
    0
end

exit(main(ARGS))
