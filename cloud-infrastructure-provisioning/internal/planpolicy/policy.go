package planpolicy

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

type plan struct {
	FormatVersion   string           `json:"format_version"`
	ResourceChanges []resourceChange `json:"resource_changes"`
}

type resourceChange struct {
	Address string `json:"address"`
	Type    string `json:"type"`
	Change  struct {
		Actions []string       `json:"actions"`
		After   map[string]any `json:"after"`
	} `json:"change"`
}

type Summary struct {
	Resources int
	Creates   int
	Updates   int
}

// Check accepts the machine-readable output of terraform show -json. It rejects
// destructive changes and public S3 access policy regressions before apply.
func Check(reader io.Reader) (Summary, error) {
	decoder := json.NewDecoder(io.LimitReader(reader, 32<<20))
	var value plan
	if err := decoder.Decode(&value); err != nil {
		return Summary{}, fmt.Errorf("decode plan JSON: %w", err)
	}
	if value.FormatVersion == "" {
		return Summary{}, fmt.Errorf("plan JSON is missing format_version")
	}
	var summary Summary
	for _, resource := range value.ResourceChanges {
		summary.Resources++
		for _, action := range resource.Change.Actions {
			switch action {
			case "create":
				summary.Creates++
			case "update":
				summary.Updates++
			case "no-op", "read":
			case "delete":
				return Summary{}, fmt.Errorf("destructive action denied for %s", resource.Address)
			default:
				return Summary{}, fmt.Errorf("unknown action %q for %s", action, resource.Address)
			}
		}
		if resource.Type == "aws_s3_bucket_public_access_block" && hasPublicAccess(resource.Change.After) {
			return Summary{}, fmt.Errorf("public S3 access is not allowed for %s", resource.Address)
		}
	}
	return summary, nil
}

func hasPublicAccess(attributes map[string]any) bool {
	for _, field := range []string{"block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"} {
		if value, ok := attributes[field].(bool); !ok || !value {
			return true
		}
	}
	return false
}

// RedactProviderDiagnostic trims likely credential-bearing values from external
// CLI output before showing it to a developer.
func RedactProviderDiagnostic(message string) string {
	for _, marker := range []string{"AWS_SECRET_ACCESS_KEY=", "AWS_SESSION_TOKEN=", "Authorization: Bearer "} {
		searchFrom := 0
		for {
			relativeStart := strings.Index(message[searchFrom:], marker)
			if relativeStart < 0 {
				break
			}
			start := searchFrom + relativeStart
			valueStart := start + len(marker)
			end := strings.IndexAny(message[valueStart:], " \t\r\n,;")
			if end < 0 {
				end = len(message) - valueStart
			}
			message = message[:valueStart] + "[REDACTED]" + message[valueStart+end:]
			searchFrom = valueStart + len("[REDACTED]")
		}
	}
	return message
}
