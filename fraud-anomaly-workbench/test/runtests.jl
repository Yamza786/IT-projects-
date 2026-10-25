using Test
using FraudAnomalyWorkbench
using SQLite

@testset "auditable fraud baseline" begin
    history = [
        Transaction("h1", 10000, "retail", 9, false, false),
        Transaction("h2", 11000, "retail", 10, false, false),
        Transaction("h3", 9000, "retail", 11, false, false),
    ]
    baseline = train_baseline(history)
    ordinary = score_transaction(baseline, Transaction("o1", 10500, "retail", 12, false, false))
    suspicious = score_transaction(baseline, Transaction("s1", 25000, "retail", 2, true, true))
    @test ordinary.flagged == false
    @test suspicious.flagged == true
    @test suspicious.z_score == 15.0
    @test suspicious.reasons == ["unusual_amount", "new_device", "country_change"]
    @test_throws ArgumentError score_transaction(baseline, Transaction("x", 100, "unknown", 3, false, false))
    @test_throws ArgumentError Transaction("../x", 100, "retail", 3, false, false)
    @test_throws ArgumentError Transaction("x", 0, "retail", 3, false, false)
end

@testset "SQL review store" begin
    db = SQLite.DB()
    try
        item = Transaction("flag-1", 9999, "retail", 2, true, false)
        score = score_transaction(train_baseline([Transaction("base", 1000, "retail", 8, false, false)]), item)
        @test save_scores!(db, [score]) == 1
        @test save_scores!(db, [score]) == 1
        rows = list_scores(db; flagged_only=true)
        @test length(rows) == 1
        @test rows[1].transaction_id == "flag-1"
        @test rows[1].review_state == "pending"
        @test review_score!(db, "flag-1", "accepted") == "accepted"
        @test list_scores(db)[1].review_state == "accepted"
        @test_throws ArgumentError review_score!(db, "missing", "rejected")
        @test_throws ArgumentError review_score!(db, "flag-1", "pending")
    finally
        close(db)
    end
end

@testset "bounded CSV import" begin
    mktemp() do path, io
        write(io, "transaction_id,amount_cents,category,hour_utc,new_device,country_change\na1,1200,retail,8,false,false\n")
        close(io)
        @test length(parse_csv(path)) == 1
    end
    mktemp() do path, io
        write(io, "wrong,header\na1,1200,retail,8,false,false\n")
        close(io)
        @test_throws ArgumentError parse_csv(path)
    end
end
