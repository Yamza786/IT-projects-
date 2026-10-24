package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/api"
	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	bind := env("SIEM_BIND", "127.0.0.1:8090")
	token := os.Getenv("SIEM_API_TOKEN")
	dataFile := env("SIEM_DATA_FILE", "./data/events.jsonl")
	if err := api.ValidateBind(bind, token); err != nil {
		logger.Error("configuration rejected", "error", err)
		os.Exit(2)
	}
	eventStore, err := store.Open(dataFile)
	if err != nil {
		logger.Error("event store unavailable", "error", err)
		os.Exit(1)
	}
	defer eventStore.Close()
	server := &http.Server{Addr: bind, Handler: api.New(eventStore, token, logger).Handler(), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16 * 1024}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
		}
	}()
	logger.Info("siem_server_start", "bind", bind, "data_file", dataFile)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
