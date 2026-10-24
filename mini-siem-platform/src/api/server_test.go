package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/store"
)

func TestHTTPAuthenticationIngestionAndTriage(t *testing.T) {
	saved, err := store.Open(filepath.Join(t.TempDir(), "events.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer saved.Close()
	server := httptest.NewServer(New(saved, "test-token", slog.New(slog.NewTextHandler(io.Discard, nil))).Handler())
	defer server.Close()
	request := func(method, path, body string, authenticated bool) *http.Response {
		req, err := http.NewRequest(method, server.URL+path, strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		if authenticated {
			req.Header.Set("Authorization", "Bearer test-token")
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		return resp
	}
	unauthorized := request(http.MethodGet, "/api/v1/alerts", "", false)
	if unauthorized.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unauthorized status=%d", unauthorized.StatusCode)
	}
	unauthorized.Body.Close()
	for i := 0; i < 5; i++ {
		input := model.Event{OccurredAt: time.Now().UTC(), Source: "auth-demo", Actor: "synthetic-user", Action: "failed_login", Outcome: "failure", SourceIP: "192.0.2.44"}
		encoded, _ := json.Marshal(input)
		resp := request(http.MethodPost, "/api/v1/events", string(encoded), true)
		if resp.StatusCode != http.StatusCreated {
			data, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			t.Fatalf("ingest %d status=%d body=%s", i, resp.StatusCode, data)
		}
		resp.Body.Close()
	}
	resp := request(http.MethodGet, "/api/v1/alerts?status=open", "", true)
	var result struct {
		Alerts []model.Alert `json:"alerts"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if len(result.Alerts) != 1 || result.Alerts[0].RuleID != "auth-failures-5m" {
		t.Fatalf("expected threshold alert: %+v", result.Alerts)
	}
	resp = request(http.MethodPatch, "/api/v1/alerts/"+result.Alerts[0].ID, `{"status":"acknowledged"}`, true)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("triage status=%d", resp.StatusCode)
	}
	resp.Body.Close()
}

func TestIngestRejectsUnknownInvalidAndOversizedRequests(t *testing.T) {
	saved, err := store.Open(filepath.Join(t.TempDir(), "events.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer saved.Close()
	handler := New(saved, "test-token", slog.New(slog.NewTextHandler(io.Discard, nil))).Handler()
	for name, body := range map[string]string{"unknown field": `{"source":"x","unexpected":true}`, "invalid outcome": fmt.Sprintf(`{"occurred_at":%q,"source":"x","actor":"a","action":"login","outcome":"unknown"}`, time.Now().UTC().Format(time.RFC3339))} {
		t.Run(name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/api/v1/events", bytes.NewBufferString(body))
			req.Header.Set("Authorization", "Bearer test-token")
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
			}
		})
	}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/events", strings.NewReader(strings.Repeat("x", 17*1024)))
	req.Header.Set("Authorization", "Bearer test-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("oversized body status=%d", rec.Code)
	}
	noScheme := httptest.NewRequest(http.MethodGet, "/api/v1/alerts", nil)
	noScheme.Header.Set("Authorization", "test-token")
	noSchemeRec := httptest.NewRecorder()
	handler.ServeHTTP(noSchemeRec, noScheme)
	if noSchemeRec.Code != http.StatusUnauthorized {
		t.Fatalf("bare token was accepted: status=%d", noSchemeRec.Code)
	}
	if err := ValidateBind("0.0.0.0:8090", "short"); err == nil {
		t.Fatal("non-loopback bind accepted a weak/missing token")
	}
	if err := ValidateBind("127.0.0.1:8090", ""); err != nil {
		t.Fatalf("loopback bind should permit no token for health-only use: %v", err)
	}
}
