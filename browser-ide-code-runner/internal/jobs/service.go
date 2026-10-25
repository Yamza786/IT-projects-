package jobs

import (
	"context"
	"errors"
	"strings"
	"sync"
	"time"
)

const (
	MaxSourceBytes = 8 * 1024
	MaxResultBytes = 16 * 1024
	MaxClientRuns  = 10
	RunTimeout     = 2 * time.Second
)

var ErrBusy = errors.New("all runner slots are busy")
var ErrQuota = errors.New("run quota exceeded; try again later")

type Runner interface {
	Run(context.Context, string) (stdout, stderr string, err error)
}

type Result struct {
	Stdout   string `json:"stdout"`
	Stderr   string `json:"stderr"`
	Duration int64  `json:"durationMs"`
}

type Service struct {
	runner Runner
	slots  chan struct{}
	mu     sync.Mutex
	usage  map[string][]time.Time
	now    func() time.Time
}

func New(runner Runner, concurrentRuns int) *Service {
	if concurrentRuns < 1 {
		concurrentRuns = 1
	}
	return &Service{runner: runner, slots: make(chan struct{}, concurrentRuns), usage: make(map[string][]time.Time), now: time.Now}
}

func (s *Service) Run(ctx context.Context, client, source string) (Result, error) {
	source = strings.TrimSpace(source)
	if source == "" || len(source) > MaxSourceBytes {
		return Result{}, errors.New("code must be between 1 and 8192 bytes")
	}
	if !s.takeQuota(client) {
		return Result{}, ErrQuota
	}
	select {
	case s.slots <- struct{}{}:
		defer func() { <-s.slots }()
	default:
		return Result{}, ErrBusy
	}

	started := s.now()
	runCtx, cancel := context.WithTimeout(ctx, RunTimeout)
	defer cancel()
	stdout, stderr, err := s.runner.Run(runCtx, source)
	result := Result{Stdout: limitOutput(stdout), Stderr: limitOutput(stderr), Duration: s.now().Sub(started).Milliseconds()}
	if runCtx.Err() != nil {
		return result, runCtx.Err()
	}
	return result, err
}

func (s *Service) takeQuota(client string) bool {
	now := s.now()
	cutoff := now.Add(-time.Hour)
	s.mu.Lock()
	defer s.mu.Unlock()
	active := s.usage[client][:0]
	for _, hit := range s.usage[client] {
		if hit.After(cutoff) {
			active = append(active, hit)
		}
	}
	if len(active) >= MaxClientRuns {
		s.usage[client] = active
		return false
	}
	s.usage[client] = append(active, now)
	return true
}

func limitOutput(value string) string {
	if len(value) <= MaxResultBytes {
		return value
	}
	return value[:MaxResultBytes] + "\n[truncated]"
}
