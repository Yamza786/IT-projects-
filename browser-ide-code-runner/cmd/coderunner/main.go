package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"browser-ide-code-runner/internal/api"
	"browser-ide-code-runner/internal/jobs"
	"browser-ide-code-runner/internal/sandbox"
)

func main() {
	addr := os.Getenv("IDE_ADDR")
	if addr == "" {
		addr = "127.0.0.1:8080"
	}
	service := jobs.New(sandbox.DockerRunner{}, 2)
	server := &http.Server{
		Addr:              addr,
		Handler:           api.New(service),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
	}
	log.Printf("browser IDE listening on %s", addr)
	log.Fatal(server.ListenAndServe())
}
