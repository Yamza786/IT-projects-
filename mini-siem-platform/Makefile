.PHONY: setup ui typecheck test build run
setup:
	npm ci
ui:
	npm run build
typecheck:
	npm run typecheck
test:
	go test -race ./...
build: ui
	go build -trimpath -o siem ./cmd/siem
run: ui
	go run ./cmd/siem
