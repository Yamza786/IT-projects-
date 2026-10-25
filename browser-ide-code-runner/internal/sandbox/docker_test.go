package sandbox

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDockerRunnerUsesRestrictedEphemeralContainer(t *testing.T) {
	log := filepath.Join(t.TempDir(), "docker-args")
	shim := filepath.Join(t.TempDir(), "docker")
	script := "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$DOCKER_ARGS_LOG\"\ncat >/dev/null\nprintf 'ok\\n'\n"
	if err := os.WriteFile(shim, []byte(script), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("DOCKER_ARGS_LOG", log)
	stdout, _, err := (DockerRunner{DockerPath: shim}).Run(context.Background(), "console.log('ok')")
	if err != nil {
		t.Fatal(err)
	}
	if stdout != "ok\n" {
		t.Fatalf("stdout = %q", stdout)
	}
	args, err := os.ReadFile(log)
	if err != nil {
		t.Fatal(err)
	}
	for _, required := range []string{"--network=none", "--memory=128m", "--cpus=0.5", "--pids-limit=32", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "node:22-alpine"} {
		if !strings.Contains(string(args), required) {
			t.Errorf("docker args missing %q", required)
		}
	}
}
