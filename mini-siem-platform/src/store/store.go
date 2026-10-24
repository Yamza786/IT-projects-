package store

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
)

const maxLineBytes = 2 << 20

type Evaluator func([]model.Event) ([]model.Alert, error)
type record struct {
	Type   string              `json:"type"`
	Event  *model.Event        `json:"event,omitempty"`
	Alerts []model.Alert       `json:"alerts,omitempty"`
	Triage *model.TriageRecord `json:"triage,omitempty"`
}

type Store struct {
	mu           sync.RWMutex
	file         *os.File
	events       []model.Event
	alerts       map[string]model.Alert
	fingerprints map[string]string
	triage       []model.TriageRecord
}

func Open(path string) (*Store, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("data file path is required")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return nil, fmt.Errorf("create data directory: %w", err)
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0600)
	if err != nil {
		return nil, fmt.Errorf("open event store: %w", err)
	}
	if err := f.Chmod(0600); err != nil {
		f.Close()
		return nil, fmt.Errorf("secure event store permissions: %w", err)
	}
	s := &Store{file: f, alerts: map[string]model.Alert{}, fingerprints: map[string]string{}}
	if err := s.load(); err != nil {
		f.Close()
		return nil, err
	}
	return s, nil
}

func (s *Store) Close() error { return s.file.Close() }

func (s *Store) load() error {
	if _, err := s.file.Seek(0, 0); err != nil {
		return err
	}
	scanner := bufio.NewScanner(s.file)
	scanner.Buffer(make([]byte, 64*1024), maxLineBytes)
	line := 0
	for scanner.Scan() {
		line++
		var item record
		if err := json.Unmarshal(scanner.Bytes(), &item); err != nil {
			return fmt.Errorf("decode event store line %d: %w", line, err)
		}
		switch item.Type {
		case "ingest":
			if item.Event == nil {
				return fmt.Errorf("event store line %d has no event", line)
			}
			s.events = append(s.events, *item.Event)
			for _, alert := range item.Alerts {
				s.alerts[alert.ID] = alert
				s.fingerprints[alert.Fingerprint] = alert.ID
			}
		case "triage":
			if item.Triage == nil {
				return fmt.Errorf("event store line %d has no triage record", line)
			}
			if alert, ok := s.alerts[item.Triage.AlertID]; ok {
				alert.Status = item.Triage.To
				alert.UpdatedAt = item.Triage.At
				s.alerts[alert.ID] = alert
			}
			s.triage = append(s.triage, *item.Triage)
		default:
			return fmt.Errorf("event store line %d has unknown record type %q", line, item.Type)
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read event store: %w", err)
	}
	_, err := s.file.Seek(0, 2)
	return err
}

func (s *Store) Ingest(event model.Event, evaluate Evaluator) ([]model.Alert, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, prior := range s.events {
		if prior.ID == event.ID {
			return nil, fmt.Errorf("event id already exists")
		}
	}
	view := append(append([]model.Event(nil), s.events...), event)
	alerts, err := evaluate(view)
	if err != nil {
		return nil, err
	}
	unique := make([]model.Alert, 0, len(alerts))
	for _, alert := range alerts {
		if _, exists := s.fingerprints[alert.Fingerprint]; !exists {
			unique = append(unique, alert)
		}
	}
	if err := s.append(record{Type: "ingest", Event: &event, Alerts: unique}); err != nil {
		return nil, err
	}
	s.events = append(s.events, event)
	for _, alert := range unique {
		s.alerts[alert.ID] = alert
		s.fingerprints[alert.Fingerprint] = alert.ID
	}
	return cloneAlerts(unique), nil
}

func (s *Store) Events(limit int) []model.Event {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	start := len(s.events) - limit
	if start < 0 {
		start = 0
	}
	result := append([]model.Event(nil), s.events[start:]...)
	for left, right := 0, len(result)-1; left < right; left, right = left+1, right-1 {
		result[left], result[right] = result[right], result[left]
	}
	return result
}

func (s *Store) Alerts(status string, limit int) []model.Alert {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	result := make([]model.Alert, 0)
	for _, alert := range s.alerts {
		if status == "" || alert.Status == status {
			result = append(result, alert)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].CreatedAt.After(result[j].CreatedAt) })
	if len(result) > limit {
		result = result[:limit]
	}
	return cloneAlerts(result)
}

func (s *Store) Triage(id, target string, now time.Time) (model.Alert, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	alert, ok := s.alerts[id]
	if !ok {
		return model.Alert{}, os.ErrNotExist
	}
	allowed := target == "acknowledged" || target == "resolved"
	if !allowed {
		return model.Alert{}, fmt.Errorf("status must be acknowledged or resolved")
	}
	if alert.Status == target {
		return alert, nil
	}
	if alert.Status == "resolved" {
		return model.Alert{}, fmt.Errorf("resolved alerts cannot change status")
	}
	change := model.TriageRecord{AlertID: id, From: alert.Status, To: target, At: now.UTC()}
	if err := s.append(record{Type: "triage", Triage: &change}); err != nil {
		return model.Alert{}, err
	}
	alert.Status, alert.UpdatedAt = target, change.At
	s.alerts[id] = alert
	s.triage = append(s.triage, change)
	return alert, nil
}

func (s *Store) append(item record) error {
	data, err := json.Marshal(item)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	start, err := s.file.Seek(0, 2)
	if err != nil {
		return fmt.Errorf("locate append point: %w", err)
	}
	written, err := s.file.Write(data)
	if err != nil || written != len(data) {
		if err == nil {
			err = fmt.Errorf("short append: wrote %d of %d bytes", written, len(data))
		}
		_ = s.file.Truncate(start)
		_, _ = s.file.Seek(0, 2)
		return fmt.Errorf("append audit record: %w", err)
	}
	if err := s.file.Sync(); err != nil {
		_ = s.file.Truncate(start)
		_, _ = s.file.Seek(0, 2)
		return fmt.Errorf("sync audit record: %w", err)
	}
	return nil
}

func cloneAlerts(alerts []model.Alert) []model.Alert {
	copyOf := make([]model.Alert, len(alerts))
	copy(copyOf, alerts)
	for i := range copyOf {
		copyOf[i].EventIDs = append([]string(nil), alerts[i].EventIDs...)
	}
	return copyOf
}

var ErrNotFound = errors.New("not found")
