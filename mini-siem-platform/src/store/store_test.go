package store

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
)

func TestFileStorePersistsEventsAlertsAndTriage(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "events.jsonl")
	s, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	event := model.Event{ID: "event-1", Actor: "operator", Action: "privilege_change", Outcome: "success", OccurredAt: time.Now().UTC()}
	alert := model.Alert{ID: "alert-1", Fingerprint: "fingerprint-1", RuleID: "privilege-change", Severity: "medium", Status: "open", EventIDs: []string{event.ID}, CreatedAt: time.Now().UTC()}
	created, err := s.Ingest(event, func([]model.Event) ([]model.Alert, error) { return []model.Alert{alert}, nil })
	if err != nil || len(created) != 1 {
		t.Fatalf("ingest: %v %+v", err, created)
	}
	updated, err := s.Triage(alert.ID, "acknowledged", time.Now())
	if err != nil || updated.Status != "acknowledged" {
		t.Fatalf("triage: %v %+v", err, updated)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	s, err = Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	if got := s.Events(10); len(got) != 1 || got[0].ID != event.ID {
		t.Fatalf("events not restored: %+v", got)
	}
	if got := s.Alerts("acknowledged", 10); len(got) != 1 || got[0].ID != alert.ID {
		t.Fatalf("triage not restored: %+v", got)
	}
}

func TestTriageRejectsInvalidTransitions(t *testing.T) {
	s, err := Open(filepath.Join(t.TempDir(), "events.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	_, err = s.Triage("absent", "resolved", time.Now())
	if err == nil {
		t.Fatal("expected unknown alert error")
	}
	_, err = s.Triage("absent", "open", time.Now())
	if err == nil {
		t.Fatal("expected invalid target error")
	}
}
