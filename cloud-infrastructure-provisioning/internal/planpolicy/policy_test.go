package planpolicy

import (
	"strings"
	"testing"
)

func TestAllowsSafePlanAndSummarizes(t *testing.T) {
	input := `{"format_version":"1.2","resource_changes":[{"address":"aws_s3_bucket.data","type":"aws_s3_bucket","change":{"actions":["create"],"after":{}}},{"address":"aws_s3_bucket_public_access_block.data","type":"aws_s3_bucket_public_access_block","change":{"actions":["create"],"after":{"block_public_acls":true,"block_public_policy":true,"ignore_public_acls":true,"restrict_public_buckets":true}}}]}`
	summary, err := Check(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	if summary.Resources != 2 || summary.Creates != 2 {
		t.Fatalf("unexpected summary: %+v", summary)
	}
}

func TestRejectsDeletesAndPublicBucketPolicy(t *testing.T) {
	for _, input := range []string{
		`{"format_version":"1.2","resource_changes":[{"address":"aws_s3_bucket.data","type":"aws_s3_bucket","change":{"actions":["delete"],"after":null}}]}`,
		`{"format_version":"1.2","resource_changes":[{"address":"aws_s3_bucket_public_access_block.data","type":"aws_s3_bucket_public_access_block","change":{"actions":["update"],"after":{"block_public_acls":false,"block_public_policy":true,"ignore_public_acls":true,"restrict_public_buckets":true}}}]}`,
	} {
		if _, err := Check(strings.NewReader(input)); err == nil {
			t.Fatalf("expected policy rejection: %s", input)
		}
	}
}

func TestRejectsMalformedOrUnboundedPlan(t *testing.T) {
	if _, err := Check(strings.NewReader(`{"resource_changes":[]}`)); err == nil {
		t.Fatal("missing format_version accepted")
	}
	if _, err := Check(strings.NewReader(`{`)); err == nil {
		t.Fatal("malformed JSON accepted")
	}
}

func TestRedactsCredentials(t *testing.T) {
	got := RedactProviderDiagnostic("failure AWS_SECRET_ACCESS_KEY=topsecret\nretry")
	if strings.Contains(got, "topsecret") || !strings.Contains(got, "[REDACTED]") {
		t.Fatalf("secret not redacted: %q", got)
	}
}
