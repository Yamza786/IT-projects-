package rules

import (
	"fmt"
	"testing"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
)

func TestFailedLoginThresholdAndPrivilegeRule(t *testing.T) {
	now := time.Date(2026, 10, 24, 12, 0, 0, 0, time.UTC)
	var events []model.Event
	for i := 0; i < 4; i++ {
		events = append(events, model.Event{ID: fmt.Sprintf("e%d", i), Actor: "alice", Action: "failed_login", Outcome: "failure", OccurredAt: now.Add(time.Duration(i) * time.Minute)})
	}
	newID := func() (string, error) { return "alert-id", nil }
	alerts, err := Evaluate(events, now, newID)
	if err != nil {
		t.Fatal(err)
	}
	if len(alerts) != 0 {
		t.Fatalf("fired before threshold: %d", len(alerts))
	}
	events = append(events, model.Event{ID: "e4", Actor: "alice", Action: "failed_login", Outcome: "failure", OccurredAt: now.Add(4 * time.Minute)})
	alerts, err = Evaluate(events, now, newID)
	if err != nil {
		t.Fatal(err)
	}
	if len(alerts) != 1 || len(alerts[0].EventIDs) != 5 {
		t.Fatalf("threshold did not produce one correlated alert: %+v", alerts)
	}
	events = append(events, model.Event{ID: "e5", Actor: "bob", Action: "privilege_change", Outcome: "success", OccurredAt: now})
	alerts, err = Evaluate(events, now, newID)
	if err != nil {
		t.Fatal(err)
	}
	if len(alerts) != 1 || alerts[0].RuleID != PrivilegeChangeRule {
		t.Fatalf("privilege rule did not fire: %+v", alerts)
	}
}
