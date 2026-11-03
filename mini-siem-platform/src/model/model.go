package model

import (
	"fmt"
	"net"
	"strings"
	"time"
)

type Event struct {
	ID         string    `json:"id"`
	OccurredAt time.Time `json:"occurred_at"`
	ReceivedAt time.Time `json:"received_at"`
	Source     string    `json:"source"`
	Actor      string    `json:"actor"`
	Action     string    `json:"action"`
	Outcome    string    `json:"outcome"`
	SourceIP   string    `json:"source_ip,omitempty"`
	Summary    string    `json:"summary,omitempty"`
}

type Alert struct {
	ID          string    `json:"id"`
	Fingerprint string    `json:"fingerprint"`
	RuleID      string    `json:"rule_id"`
	Severity    string    `json:"severity"`
	Title       string    `json:"title"`
	EventIDs    []string  `json:"event_ids"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type TriageRecord struct {
	AlertID string    `json:"alert_id"`
	From    string    `json:"from"`
	To      string    `json:"to"`
	At      time.Time `json:"at"`
}

func Normalize(input Event, now time.Time, newID func() (string, error)) (Event, error) {
	if len(input.Source) > 80 || len(input.Actor) > 120 || len(input.Action) > 80 || len(input.Summary) > 500 {
		return Event{}, fmt.Errorf("event field exceeds maximum length")
	}
	input.Source = strings.TrimSpace(input.Source)
	input.Actor = strings.TrimSpace(input.Actor)
	input.Action = strings.ToLower(strings.TrimSpace(input.Action))
	input.Outcome = strings.ToLower(strings.TrimSpace(input.Outcome))
	input.Summary = strings.TrimSpace(input.Summary)
	if input.Source == "" || input.Actor == "" || input.Action == "" {
		return Event{}, fmt.Errorf("source, actor, and action are required")
	}
	if input.ID != "" {
		if len(input.ID) > 80 {
			return Event{}, fmt.Errorf("event id exceeds maximum length")
		}
		for _, char := range input.ID {
			if !(char >= 'a' && char <= 'z' || char >= 'A' && char <= 'Z' || char >= '0' && char <= '9' || char == '-' || char == '_' || char == '.') {
				return Event{}, fmt.Errorf("event id contains unsupported characters")
			}
		}
	}
	if input.Outcome != "success" && input.Outcome != "failure" && input.Outcome != "denied" {
		return Event{}, fmt.Errorf("outcome must be success, failure, or denied")
	}
	if input.SourceIP != "" && net.ParseIP(input.SourceIP) == nil {
		return Event{}, fmt.Errorf("source_ip must be an IP address")
	}
	if input.OccurredAt.IsZero() || input.OccurredAt.After(now.Add(5*time.Minute)) || input.OccurredAt.Before(now.Add(-30*24*time.Hour)) {
		return Event{}, fmt.Errorf("occurred_at must be within the last 30 days and no more than 5 minutes in the future")
	}
	if input.ID == "" {
		id, err := newID()
		if err != nil {
			return Event{}, fmt.Errorf("create event id: %w", err)
		}
		input.ID = id
	}
	input.ReceivedAt = now.UTC()
	input.OccurredAt = input.OccurredAt.UTC()
	return input, nil
}
