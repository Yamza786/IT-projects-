package sandbox

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"strings"
)

const maxOutput = 16 * 1024

// DockerRunner executes JavaScript in an ephemeral, offline, resource-limited container.
type DockerRunner struct {
	DockerPath string
	Image      string
}

type resultBuffer struct {
	bytes.Buffer
	truncated bool
}

func (b *resultBuffer) Write(p []byte) (int, error) {
	remaining := maxOutput - b.Len()
	if remaining <= 0 {
		b.truncated = true
		return len(p), nil
	}
	if len(p) > remaining {
		_, _ = b.Buffer.Write(p[:remaining])
		b.truncated = true
		return len(p), nil
	}
	return b.Buffer.Write(p)
}

// Run starts a fresh container for each snippet. Source is passed over stdin, never mounted.
func (r DockerRunner) Run(ctx context.Context, source string) (string, string, error) {
	docker := r.DockerPath
	if docker == "" {
		docker = "docker"
	}
	image := r.Image
	if image == "" {
		image = "node:22-alpine"
	}
	args := []string{
		"run", "--rm", "--network=none", "--memory=128m", "--memory-swap=128m", "--cpus=0.5", "--pids-limit=32",
		"--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=8m", "--user=65534:65534",
		"--security-opt=no-new-privileges", "--cap-drop=ALL", "--log-driver=none",
		"--env", "HOME=/tmp", "--interactive", image, "node", "--input-type=commonjs", "-",
	}
	cmd := exec.CommandContext(ctx, docker, args...)
	cmd.Stdin = strings.NewReader(source)
	stdout, stderr := &resultBuffer{}, &resultBuffer{}
	cmd.Stdout, cmd.Stderr = stdout, stderr
	err := cmd.Run()
	if stdout.truncated || stderr.truncated {
		return stdout.String(), stderr.String(), errors.New("output exceeded 16 KiB per stream")
	}
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			return stdout.String(), stderr.String(), fmt.Errorf("snippet exited with status %d", exitErr.ExitCode())
		}
		return stdout.String(), stderr.String(), fmt.Errorf("start sandbox: %w", err)
	}
	return stdout.String(), stderr.String(), nil
}
