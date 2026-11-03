package rules

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strings"
	"time"

	"github.com/Yamza786/IT-projects-/mini-siem-platform/src/model"
)

const FailedLoginRule = "auth-failures-5m"
const PrivilegeChangeRule = "privilege-change"

func Evaluate(events []model.Event, now time.Time, newID func() (string, error)) ([]model.Alert, error) {
	if len(events) == 0 {
		return nil, nil
	}
	current := events[len(events)-1]
	var found []model.Alert
	if current.Action == "failed_login" && current.Outcome == "failure" {
		cutoff := current.OccurredAt.Add(-5 * time.Minute)
		var matched []model.Event
		for _, event := range events {
			if event.Actor == current.Actor && event.Action == "failed_login" && event.Outcome == "failure" && !event.OccurredAt.Before(cutoff) && !event.OccurredAt.After(current.OccurredAt) {
				matched = append(matched, event)
			}
		}
		if len(matched) >= 5 {
			ids := eventIDs(matched)
			fingerprint := fingerprint(FailedLoginRule, current.Actor, cutoff.Truncate(5*time.Minute).Format(time.RFC3339))
			alertID, err := newID()
			if err != nil {
				return nil, err
			}
			found = append(found, model.Alert{ID: alertID, Fingerprint: fingerprint, RuleID: FailedLoginRule, Severity: "high", Title: "Repeated authentication failures for " + current.Actor, EventIDs: ids, Status: "open", CreatedAt: now.UTC(), UpdatedAt: now.UTC()})
		}
	}
	if current.Action == "privilege_change" && (current.Outcome == "success" || current.Outcome == "denied") {
		alertID, err := newID()
		if err != nil {
			return nil, err
		}
		found = append(found, model.Alert{ID: alertID, Fingerprint: fingerprint(PrivilegeChangeRule, current.Actor, current.ID), RuleID: PrivilegeChangeRule, Severity: "medium", Title: "Privilege change activity by " + current.Actor, EventIDs: []string{current.ID}, Status: "open", CreatedAt: now.UTC(), UpdatedAt: now.UTC()})
	}
	return found, nil
}

func eventIDs(events []model.Event) []string {
	ids := make([]string, 0, len(events))
	for _, event := range events {
		ids = append(ids, event.ID)
	}
	sort.Strings(ids)
	return ids
}

func fingerprint(parts ...string) string {
	hash := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(hash[:])
}
