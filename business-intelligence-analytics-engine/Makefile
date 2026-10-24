.PHONY: test init demo report

test:
	Rscript tests/testthat.R

init:
	Rscript scripts/bi.R init

demo:
	Rscript scripts/bi.R import --csv fixtures/transactions.synthetic.csv

report:
	Rscript scripts/bi.R report
