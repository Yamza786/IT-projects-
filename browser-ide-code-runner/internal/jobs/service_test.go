package jobs

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

type fakeRunner struct {
	run func(context.Context, string) (string, string, error)
}

func (f fakeRunner) Run(ctx context.Context, code string) (string, string, error) {
	return f.run(ctx, code)
}

func TestServiceValidatesSourceAndBoundsConcurrency(t *testing.T) {
	started, release := make(chan struct{}), make(chan struct{})
	service := New(fakeRunner{run: func(context.Context, string) (string, string, error) {
		close(started)
		<-release
		return "ok", "", nil
	}}, 1)
	first := make(chan error, 1)
	go func() { _, err := service.Run(context.Background(), "client-a", "console.log(1)"); first <- err }()
	<-started
	if _, err := service.Run(context.Background(), "client-b", "console.log(2)"); !errors.Is(err, ErrBusy) {
		t.Fatalf("expected bounded runner, got %v", err)
	}
	close(release)
	if err := <-first; err != nil {
		t.Fatal(err)
	}
	if _, err := service.Run(context.Background(), "client-c", strings.Repeat("x", MaxSourceBytes+1)); err == nil {
		t.Fatal("oversized source was accepted")
	}
}

func TestServiceEnforcesPerClientQuotaAndExpiresOldRuns(t *testing.T) {
	service := New(fakeRunner{run: func(context.Context, string) (string, string, error) { return "", "", nil }}, 1)
	now := time.Unix(1_800_000_000, 0)
	service.now = func() time.Time { return now }
	for i := 0; i < MaxClientRuns; i++ {
		if _, err := service.Run(context.Background(), "client", "1+1"); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := service.Run(context.Background(), "client", "1+1"); !errors.Is(err, ErrQuota) {
		t.Fatalf("expected quota error, got %v", err)
	}
	now = now.Add(time.Hour + time.Second)
	if _, err := service.Run(context.Background(), "client", "1+1"); err != nil {
		t.Fatalf("quota did not expire: %v", err)
	}
}

func TestServiceTimesOutAndCapsOutput(t *testing.T) {
	service := New(fakeRunner{run: func(ctx context.Context, _ string) (string, string, error) {
		<-ctx.Done()
		return strings.Repeat("x", MaxResultBytes+1), "", ctx.Err()
	}}, 1)
	result, err := service.Run(context.Background(), "client", "while (true) {}")
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected timeout, got %v", err)
	}
	if len(result.Stdout) > MaxResultBytes+20 {
		t.Fatalf("output was not bounded: %d bytes", len(result.Stdout))
	}
}
