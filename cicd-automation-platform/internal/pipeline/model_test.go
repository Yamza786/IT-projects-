package pipeline

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const validYAML = `name: sample
version: 1
jobs:
  - id: build
    image: alpine:3.22
    steps:
      - name: build
        run: echo ok
  - id: test
    image: alpine:3.22
    needs: [build]
    steps:
      - name: test
        run: echo passed
`

func TestLoadPipelineAndDependencies(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pipeline.yaml")
	if err := os.WriteFile(path, []byte(validYAML), 0o600); err != nil {
		t.Fatal(err)
	}
	definition, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := definition.Jobs[1].Needs[0]; got != "build" {
		t.Fatalf("dependency = %q, want build", got)
	}
}

func TestRejectUnknownFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pipeline.yaml")
	if err := os.WriteFile(path, []byte(strings.Replace(validYAML, "version: 1", "version: 1\nunknown: true", 1)), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil || !strings.Contains(err.Error(), "field unknown not found") {
		t.Fatalf("Load error = %v, want unknown-field error", err)
	}
}

func TestRejectDependencyDeclaredLater(t *testing.T) {
	definition, err := Load(writePipeline(t, strings.Replace(validYAML, "  - id: build", "  - id: build", 1)))
	if err != nil || len(definition.Jobs) != 2 {
		t.Fatalf("valid pipeline failed: %v", err)
	}
	definition.Jobs[0].Needs = []string{"test"}
	if err := Validate(definition); err == nil {
		t.Fatal("expected forward dependency rejection")
	}
}

func TestRejectLatestImageAndWorkspaceEscape(t *testing.T) {
	definition, err := Load(writePipeline(t, validYAML))
	if err != nil {
		t.Fatal(err)
	}
	definition.Jobs[0].Image = "alpine:latest"
	if err := Validate(definition); err == nil {
		t.Fatal("expected mutable latest tag rejection")
	}
	for _, candidate := range []string{"../secret", "/tmp/file", "a/../../secret", "report?.txt"} {
		if err := ValidateWorkspacePath(candidate); err == nil {
			t.Errorf("ValidateWorkspacePath(%q) unexpectedly succeeded", candidate)
		}
	}
}

func TestRejectMultipleYamlDocuments(t *testing.T) {
	if _, err := Load(writePipeline(t, validYAML+"---\nname: second\n")); err == nil {
		t.Fatal("expected multiple document rejection")
	}
}

func writePipeline(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "pipeline.yaml")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}
