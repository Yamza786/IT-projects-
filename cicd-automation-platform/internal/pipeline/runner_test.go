package pipeline

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunRecordsArtifactsAndUsesConstrainedDocker(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "input.txt"), []byte("preserve"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "report.txt"), []byte("synthetic artifact"), 0o600); err != nil {
		t.Fatal(err)
	}
	dockerDir := t.TempDir()
	argumentsFile := filepath.Join(root, "docker-args.txt")
	docker := filepath.Join(dockerDir, "docker")
	if err := os.WriteFile(docker, []byte("#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$DOCKER_ARGS_FILE\"\nprintf 'fake worker completed\\n'\n"), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("DOCKER_ARGS_FILE", argumentsFile)
	t.Setenv("PATH", dockerDir+string(os.PathListSeparator)+os.Getenv("PATH"))
	definition := Definition{Name: "runner-test", Version: 1, Jobs: []Job{{
		ID: "build", Image: "alpine:3.22", Steps: []Step{{Name: "show", Run: "echo ok"}},
		Artifacts: []string{"report.txt"},
	}}}
	record, err := Run(definition, root)
	if err != nil {
		t.Fatal(err)
	}
	if record.Status != "success" || record.Jobs[0].Status != "success" || !strings.Contains(record.Jobs[0].Output, "fake worker") {
		t.Fatalf("unexpected run record: %+v", record)
	}
	arguments, err := os.ReadFile(argumentsFile)
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{"--network=none", "--read-only", "--cap-drop=ALL", "--memory=512m", "alpine:3.22", "echo ok"} {
		if !strings.Contains(string(arguments), expected) {
			t.Errorf("Docker arguments missing %q: %s", expected, arguments)
		}
	}
	if len(record.Jobs[0].Artifacts) != 1 || record.Jobs[0].Artifacts[0].Bytes != int64(len("synthetic artifact")) {
		t.Fatalf("artifact record = %+v", record.Jobs[0].Artifacts)
	}
	storedArtifact := filepath.Join(root, ".pipeline", "runs", record.ID, filepath.FromSlash(record.Jobs[0].Artifacts[0].Stored))
	if _, err := os.Stat(storedArtifact); err != nil {
		t.Fatalf("stored artifact was not written: %v", err)
	}
	original, err := os.ReadFile(filepath.Join(root, "input.txt"))
	if err != nil || string(original) != "preserve" {
		t.Fatalf("source workspace was changed: %q, %v", original, err)
	}
}

func TestRunSkipsDependentJobAfterFailure(t *testing.T) {
	root := t.TempDir()
	dockerDir := t.TempDir()
	docker := filepath.Join(dockerDir, "docker")
	if err := os.WriteFile(docker, []byte("#!/bin/sh\nexit 1\n"), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dockerDir+string(os.PathListSeparator)+os.Getenv("PATH"))
	definition := Definition{Name: "failure-test", Version: 1, Jobs: []Job{
		{ID: "build", Image: "alpine:3.22", Steps: []Step{{Name: "fails", Run: "false"}}},
		{ID: "test", Image: "alpine:3.22", Needs: []string{"build"}, Steps: []Step{{Name: "test", Run: "true"}}},
	}}
	record, err := Run(definition, root)
	if err == nil || record.Status != "failed" || record.Jobs[1].Status != "skipped" {
		t.Fatalf("record=%+v err=%v, wanted failure and skipped dependent", record, err)
	}
}
