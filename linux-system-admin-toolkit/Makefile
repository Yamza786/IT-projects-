.PHONY: test lint

test:
	bash tests/run.sh

lint:
	shellcheck bin/syscare tests/run.sh
	bash -n bin/syscare tests/run.sh
