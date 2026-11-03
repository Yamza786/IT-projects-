package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

type Result struct {
	Target string `json:"target"`
	Check  string `json:"check"`
	OK     bool   `json:"ok"`
	Millis int64  `json:"duration_ms"`
	Error  string `json:"error,omitempty"`
}

func main() {
	target := flag.String("target", "", "one explicitly authorized hostname or IP (no ranges/scanning)")
	port := flag.Int("tcp", 0, "optional single TCP port, 1-65535")
	endpoint := flag.String("http", "", "optional HTTP(S) URL on the target host")
	timeout := flag.Duration("timeout", 3*time.Second, "per-check timeout (100ms-10s)")
	flag.Parse()
	if *target == "" || *timeout < 100*time.Millisecond || *timeout > 10*time.Second || (*port != 0 && validatePort(*port) != nil) {
		fmt.Fprintln(os.Stderr, "usage: network-monitor -target HOST [-tcp PORT] [-http URL] [-timeout 3s]")
		os.Exit(2)
	}
	host := strings.Trim(strings.TrimSpace(*target), "[]")
	if err := validateHost(host); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	results := []Result{checkDNS(ctx, host)}
	cancel()
	if *port > 0 {
		ctx, cancel = context.WithTimeout(context.Background(), *timeout)
		results = append(results, checkTCP(ctx, host, *port))
		cancel()
	}
	if *endpoint != "" {
		ctx, cancel = context.WithTimeout(context.Background(), *timeout)
		results = append(results, checkHTTP(ctx, host, *endpoint))
		cancel()
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(results); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func validateHost(host string) error {
	if len(host) == 0 || len(host) > 253 || strings.ContainsAny(host, " /\\\t\r\n") {
		return fmt.Errorf("invalid host; supply exactly one hostname or IP")
	}
	if net.ParseIP(host) != nil {
		return nil
	}
	for _, label := range strings.Split(host, ".") {
		if len(label) == 0 || len(label) > 63 || label[0] == '-' || label[len(label)-1] == '-' {
			return fmt.Errorf("invalid DNS hostname")
		}
		for _, r := range label {
			if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-') {
				return fmt.Errorf("invalid DNS hostname")
			}
		}
	}
	return nil
}

func validatePort(port int) error {
	if port < 1 || port > 65535 {
		return fmt.Errorf("port must be between 1 and 65535")
	}
	return nil
}

func checkDNS(ctx context.Context, host string) Result {
	start := time.Now()
	_, err := net.DefaultResolver.LookupHost(ctx, host)
	return result(host, "dns", start, err)
}

func checkTCP(ctx context.Context, host string, port int) Result {
	start := time.Now()
	conn, err := (&net.Dialer{}).DialContext(ctx, "tcp", net.JoinHostPort(host, strconv.Itoa(port)))
	if err == nil {
		_ = conn.Close()
	}
	return result(host, "tcp", start, err)
}

func checkHTTP(ctx context.Context, host, rawURL string) Result {
	start := time.Now()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return result(host, "http", start, err)
	}
	if req.URL.Scheme != "https" && req.URL.Scheme != "http" {
		return result(host, "http", start, fmt.Errorf("only http and https are allowed"))
	}
	if req.URL.User != nil {
		return result(host, "http", start, fmt.Errorf("URL credentials are not allowed"))
	}
	if !strings.EqualFold(req.URL.Hostname(), host) {
		return result(host, "http", start, fmt.Errorf("URL host must match -target"))
	}
	client := &http.Client{Timeout: 10 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}
	resp, err := client.Do(req)
	if err == nil {
		_ = resp.Body.Close()
		if resp.StatusCode >= 500 {
			err = fmt.Errorf("server returned %s", resp.Status)
		}
	}
	return result(host, "http", start, err)
}

func result(host, check string, start time.Time, err error) Result {
	r := Result{Target: host, Check: check, OK: err == nil, Millis: time.Since(start).Milliseconds()}
	if err != nil {
		r.Error = err.Error()
	}
	return r
}
