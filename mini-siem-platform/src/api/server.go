package api

import (
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log/slog"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/rules"
	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/store"
)

//go:embed web/*
var assets embed.FS

type EventStore interface {
	Ingest(model.Event, store.Evaluator) ([]model.Alert, error)
	Events(int) []model.Event
	Alerts(string, int) []model.Alert
	Triage(string, string, time.Time) (model.Alert, error)
}

type Server struct {
	store  EventStore
	token  string
	logger *slog.Logger
	assets http.Handler
}

func New(eventStore EventStore, token string, logger *slog.Logger) *Server {
	if logger == nil {
		logger = slog.Default()
	}
	webFiles, _ := fs.Sub(assets, "web")
	return &Server{store: eventStore, token: token, logger: logger, assets: http.FileServer(http.FS(webFiles))}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/health", s.health)
	mux.HandleFunc("POST /api/v1/events", s.authorize(s.ingest))
	mux.HandleFunc("GET /api/v1/events", s.authorize(s.events))
	mux.HandleFunc("GET /api/v1/alerts", s.authorize(s.alerts))
	mux.HandleFunc("PATCH /api/v1/alerts/{id}", s.authorize(s.triage))
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			http.ServeFileFS(w, r, assets, "web/index.html")
			return
		}
		if strings.HasPrefix(r.URL.Path, "/web/") {
			http.StripPrefix("/web/", s.assets).ServeHTTP(w, r)
			return
		}
		http.NotFound(w, r)
	})
	return s.requestLog(securityHeaders(mux))
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "mini-siem"})
}

func (s *Server) ingest(w http.ResponseWriter, r *http.Request) {
	var input model.Event
	if err := decodeJSON(w, r, &input, 16*1024); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	now := time.Now().UTC()
	event, err := model.Normalize(input, now, model.NewID)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_event", err.Error())
		return
	}
	alerts, err := s.store.Ingest(event, func(events []model.Event) ([]model.Alert, error) { return rules.Evaluate(events, now, model.NewID) })
	if err != nil {
		if strings.Contains(err.Error(), "already exists") {
			writeError(w, http.StatusConflict, "duplicate_event", "event id already exists")
			return
		}
		s.logger.Error("event persistence failed", "error", err)
		writeError(w, http.StatusInternalServerError, "storage_error", "event could not be persisted")
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"event": event, "alerts": alerts})
}

func (s *Server) events(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"events": s.store.Events(parseLimit(r))})
}

func (s *Server) alerts(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	if status != "" && status != "open" && status != "acknowledged" && status != "resolved" {
		writeError(w, http.StatusBadRequest, "invalid_status", "status must be open, acknowledged, or resolved")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"alerts": s.store.Alerts(status, parseLimit(r))})
}

func (s *Server) triage(w http.ResponseWriter, r *http.Request) {
	var input struct {
		Status string `json:"status"`
	}
	if err := decodeJSON(w, r, &input, 1024); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	alert, err := s.store.Triage(r.PathValue("id"), input.Status, time.Now().UTC())
	if errors.Is(err, os.ErrNotExist) {
		writeError(w, http.StatusNotFound, "alert_not_found", "alert does not exist")
		return
	}
	if err != nil {
		writeError(w, http.StatusConflict, "invalid_transition", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]model.Alert{"alert": alert})
}

func (s *Server) authorize(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if s.token == "" {
			writeError(w, http.StatusServiceUnavailable, "auth_not_configured", "configure SIEM_API_TOKEN before using the API")
			return
		}
		header := r.Header.Get("Authorization")
		if !strings.HasPrefix(header, "Bearer ") {
			writeError(w, http.StatusUnauthorized, "unauthorized", "valid bearer token required")
			return
		}
		provided := strings.TrimPrefix(header, "Bearer ")
		if len(provided) != len(s.token) || subtle.ConstantTimeCompare([]byte(provided), []byte(s.token)) != 1 {
			writeError(w, http.StatusUnauthorized, "unauthorized", "valid bearer token required")
			return
		}
		next(w, r)
	}
}

func (s *Server) requestLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &statusWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(wrapped, r)
		s.logger.Info("http_request", "method", r.Method, "path", r.URL.Path, "status", wrapped.status, "duration_ms", time.Since(start).Milliseconds())
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
		next.ServeHTTP(w, r)
	})
}

func decodeJSON(w http.ResponseWriter, r *http.Request, target any, maxBytes int64) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		if err == nil {
			return fmt.Errorf("request must contain one JSON object")
		}
		return err
	}
	return nil
}

func parseLimit(r *http.Request) int {
	value, err := strconv.Atoi(r.URL.Query().Get("limit"))
	if err != nil || value <= 0 || value > 500 {
		return 100
	}
	return value
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code, "message": message}})
}
func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func ValidateBind(bind, token string) error {
	if bind == "" {
		return fmt.Errorf("bind address is required")
	}
	host, _, err := net.SplitHostPort(bind)
	if err != nil {
		return fmt.Errorf("invalid bind address: %w", err)
	}
	loopback := host == "localhost"
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		loopback = true
	}
	if !loopback && len(token) < 32 {
		return fmt.Errorf("non-loopback bind requires SIEM_API_TOKEN of at least 32 characters")
	}
	return nil
}
