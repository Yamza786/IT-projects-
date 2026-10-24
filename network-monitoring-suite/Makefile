.PHONY: test test-go test-c build
test: test-go test-c
test-go:
	go test ./...
test-c:
	$(CC) -std=c11 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -g native/checksum.c native/checksum_test.c -o checksum-test
	./checksum-test
	rm -f checksum-test
build:
	go build -o network-monitor .
