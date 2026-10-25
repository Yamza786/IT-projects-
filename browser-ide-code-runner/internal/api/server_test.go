package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"browser-ide-code-runner/internal/jobs"
)

type fakeService struct {
	result jobs.Result
	err    error
	code   string
}

func (f *fakeService) Run(_ context.Context, _ string, code string) (jobs.Result, error) {
	f.code = code
	return f.result, f.err
}

func TestRunEndpointRequiresLocalJSONAndValidBody(t *testing.T) {
	service := &fakeService{result: jobs.Result{Stdout: "2"}}
	handler := New(service)
	request := httptest.NewRequest(http.MethodPost, "/api/runs", strings.NewReader(`{"code":"console.log(1 + 1)"}`))
	request.RemoteAddr = "127.0.0.1:12345"
	request.Host = "127.0.0.1:8080"
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), `"stdout":"2"`) {
		t.Fatalf("unexpected response: %d %s", response.Code, response.Body.String())
	}
	if service.code != "console.log(1 + 1)" {
		t.Fatalf("code sent to service: %q", service.code)
	}
	if response.Header().Get("Content-Security-Policy") == "" {
		t.Fatal("security headers missing")
	}

	request = httptest.NewRequest(http.MethodPost, "/api/runs", strings.NewReader(`{"code":"1"}`))
	request.RemoteAddr = "203.0.113.10:12345"
	request.Host = "127.0.0.1:8080"
	request.Header.Set("Content-Type", "application/json")
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatalf("non-local client received status %d", response.Code)
	}

	request = httptest.NewRequest(http.MethodPost, "/api/runs", strings.NewReader(`{"code":"1","admin":true}`))
	request.RemoteAddr = "127.0.0.1:12345"
	request.Host = "127.0.0.1:8080"
	request.Header.Set("Content-Type", "application/json")
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("unknown field received status %d", response.Code)
	}
}

func TestRunEndpointMapsQuotaAndBusyErrors(t *testing.T) {
	for _, item := range []struct {
		err    error
		status int
	}{{jobs.ErrQuota, http.StatusTooManyRequests}, {jobs.ErrBusy, http.StatusServiceUnavailable}} {
		handler := New(&fakeService{err: item.err})
		request := httptest.NewRequest(http.MethodPost, "/api/runs", strings.NewReader(`{"code":"1"}`))
		request.RemoteAddr = "[::1]:12345"
		request.Host = "[::1]:8080"
		request.Header.Set("Content-Type", "application/json")
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, request)
		if response.Code != item.status {
			t.Errorf("error %v returned status %d; want %d", item.err, response.Code, item.status)
		}
	}
}

func TestRunEndpointRejectsOversizedBody(t *testing.T) {
	request := httptest.NewRequest(http.MethodPost, "/api/runs", strings.NewReader(`{"code":"`+strings.Repeat("x", jobs.MaxSourceBytes+2048)+`"}`))
	request.RemoteAddr = "127.0.0.1:12345"
	request.Host = "127.0.0.1:8080"
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	New(&fakeService{}).ServeHTTP(response, request)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("oversized body received status %d", response.Code)
	}
}

func TestLocalHostGuardRejectsDnsRebindingHost(t *testing.T) {
	request := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	request.Host = "attacker.example"
	response := httptest.NewRecorder()
	New(&fakeService{}).ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatalf("untrusted host received status %d", response.Code)
	}
}
