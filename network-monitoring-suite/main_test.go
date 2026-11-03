package main

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestValidateHost(t *testing.T) {
	for _, tc := range []struct {
		host string
		want bool
	}{{"localhost", true}, {"127.0.0.1", true}, {"example.org", true}, {"a b", false}, {"-bad.example", false}, {"example.org/", false}, {"", false}} {
		t.Run(tc.host, func(t *testing.T) {
			if got := validateHost(tc.host) == nil; got != tc.want {
				t.Fatalf("valid=%v, want %v", got, tc.want)
			}
		})
	}
}

func TestTCPCheckAgainstLocalFixture(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	port := listener.Addr().(*net.TCPAddr).Port
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	got := checkTCP(ctx, "127.0.0.1", port)
	if !got.OK {
		t.Fatalf("local TCP probe failed: %+v", got)
	}
}

func TestHTTPCheckRestrictsHostAndAvoidsRedirectFollowing(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, "/elsewhere", http.StatusFound) }))
	defer server.Close()
	host := server.Listener.Addr().(*net.TCPAddr).IP.String()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	got := checkHTTP(ctx, host, server.URL)
	if !got.OK {
		t.Fatalf("expected local 302 check to be reachable: %+v", got)
	}
	bad := checkHTTP(ctx, "example.org", server.URL)
	if bad.OK {
		t.Fatal("accepted URL for a different host")
	}
}

func TestSinglePortBound(t *testing.T) {
	for _, port := range []int{1, 65535} {
		if err := validatePort(port); err != nil {
			t.Fatalf("port %d rejected: %v", port, err)
		}
	}
	for _, port := range []int{0, -1, 65536} {
		if validatePort(port) == nil {
			t.Fatalf("port %d should be rejected", port)
		}
	}
}
