package model

import (
	"testing"
	"time"
)

func TestNormalizeSanitizesAndRejectsInvalidEvents(t *testing.T) {
	now := time.Date(2026, 10, 24, 12, 0, 0, 0, time.UTC)
	valid := Event{OccurredAt: now, Source: "  auth  ", Actor: " alice ", Action: " FAILED_LOGIN ", Outcome: " FAILURE ", SourceIP: "192.0.2.7"}
	got, err := Normalize(valid, now, func() (string, error) { return "event-1", nil })
	if err != nil {
		t.Fatal(err)
	}
	if got.Source != "auth" || got.Actor != "alice" || got.Action != "failed_login" || got.ID != "event-1" {
		t.Fatalf("unexpected normalized event: %+v", got)
	}
	for name, mutate := range map[string]func(*Event){
		"bad outcome": func(e *Event) { e.Outcome = "maybe" },
		"bad IP":      func(e *Event) { e.SourceIP = "not-an-ip" },
		"future":      func(e *Event) { e.OccurredAt = now.Add(6 * time.Minute) },
		"empty actor": func(e *Event) { e.Actor = " " },
	} {
		t.Run(name, func(t *testing.T) {
			event := valid
			mutate(&event)
			if _, err := Normalize(event, now, NewID); err == nil {
				t.Fatal("expected validation error")
			}
		})
	}
}
