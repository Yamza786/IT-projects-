.PHONY: test lint build validate

test:
	go test ./...

lint:
	go vet ./...

build:
	go build -o infraguard ./cmd/infraguard

validate:
	go run ./cmd/infraguard validate terraform
