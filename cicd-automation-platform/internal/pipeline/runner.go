package pipeline

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const maxCapturedOutput = 256 * 1024

type ArtifactRecord struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Bytes  int64  `json:"bytes"`
	Stored string `json:"stored"`
}

type JobRecord struct {
	ID         string           `json:"id"`
	Status     string           `json:"status"`
	StartedAt  time.Time        `json:"started_at,omitempty"`
	FinishedAt time.Time        `json:"finished_at,omitempty"`
	Output     string           `json:"output,omitempty"`
	Error      string           `json:"error,omitempty"`
	Artifacts  []ArtifactRecord `json:"artifacts,omitempty"`
}

type RunRecord struct {
	ID         string      `json:"id"`
	Pipeline   string      `json:"pipeline"`
	Status     string      `json:"status"`
	StartedAt  time.Time   `json:"started_at"`
	FinishedAt time.Time   `json:"finished_at"`
	Jobs       []JobRecord `json:"jobs"`
}

type cappedBuffer struct {
	data []byte
}

func (buffer *cappedBuffer) Write(value []byte) (int, error) {
	originalLength := len(value)
	remaining := maxCapturedOutput - len(buffer.data)
	if remaining > 0 {
		if len(value) > remaining {
			value = value[:remaining]
		}
		buffer.data = append(buffer.data, value...)
	}
	return originalLength, nil
}

func Run(definition Definition, workspace string) (RunRecord, error) {
	if err := Validate(definition); err != nil {
		return RunRecord{}, err
	}
	root, err := filepath.Abs(workspace)
	if err != nil {
		return RunRecord{}, fmt.Errorf("resolve workspace: %w", err)
	}
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return RunRecord{}, fmt.Errorf("resolve workspace links: %w", err)
	}
	if strings.ContainsAny(root, ",:") {
		return RunRecord{}, errors.New("workspace path cannot contain comma or colon for Docker mount syntax")
	}
	snapshot, err := os.MkdirTemp("", "cicd-worker-")
	if err != nil {
		return RunRecord{}, fmt.Errorf("create worker workspace: %w", err)
	}
	defer os.RemoveAll(snapshot)
	if err := copyWorkspace(root, snapshot); err != nil {
		return RunRecord{}, fmt.Errorf("prepare worker workspace: %w", err)
	}
	runID, err := newRunID()
	if err != nil {
		return RunRecord{}, err
	}
	runRoot := filepath.Join(root, ".pipeline", "runs", runID)
	if err := createPrivateDirectories(filepath.Join(runRoot, "artifacts")); err != nil {
		return RunRecord{}, fmt.Errorf("create run record directory: %w", err)
	}
	record := RunRecord{ID: runID, Pipeline: definition.Name, Status: "success", StartedAt: time.Now().UTC()}
	jobStatuses := make(map[string]string, len(definition.Jobs))
	for _, job := range definition.Jobs {
		jobRecord := JobRecord{ID: job.ID, Status: "running", StartedAt: time.Now().UTC()}
		blocked := false
		for _, dependency := range job.Needs {
			if jobStatuses[dependency] != "success" {
				blocked = true
				break
			}
		}
		if blocked {
			jobRecord.Status = "skipped"
			jobRecord.Error = "dependency did not succeed"
		} else {
			jobRecord.Output, err = executeJob(job, snapshot)
			if err != nil {
				jobRecord.Status = "failed"
				jobRecord.Error = err.Error()
				record.Status = "failed"
			} else {
				jobRecord.Artifacts, err = collectArtifacts(snapshot, runRoot, job)
				if err != nil {
					jobRecord.Status = "failed"
					jobRecord.Error = err.Error()
					record.Status = "failed"
				} else {
					jobRecord.Status = "success"
				}
			}
		}
		jobRecord.FinishedAt = time.Now().UTC()
		jobStatuses[job.ID] = jobRecord.Status
		record.Jobs = append(record.Jobs, jobRecord)
	}
	record.FinishedAt = time.Now().UTC()
	if err := writeRecord(filepath.Join(runRoot, "run.json"), record); err != nil {
		return record, fmt.Errorf("write run record: %w", err)
	}
	if record.Status != "success" {
		return record, fmt.Errorf("pipeline run %s failed; see %s", record.ID, filepath.Join(runRoot, "run.json"))
	}
	return record, nil
}

func executeJob(job Job, workspace string) (string, error) {
	jobContext, cancel := context.WithTimeout(context.Background(), time.Duration(job.TimeoutMinutes)*time.Minute)
	defer cancel()
	arguments := []string{
		"run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
		"--security-opt=no-new-privileges", "--pids-limit=64", "--memory=512m", "--cpus=1",
		"--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--user", fmt.Sprintf("%d:%d", os.Getuid(), os.Getgid()),
		"--workdir", "/workspace", "--entrypoint=/bin/sh", "--mount", "type=bind,src=" + workspace + ",dst=/workspace",
		job.Image, "-eu", "-c", stepScript(job.Steps),
	}
	command := exec.CommandContext(jobContext, "docker", arguments...)
	command.Dir = workspace
	output := &cappedBuffer{}
	command.Stdout = output
	command.Stderr = output
	err := command.Run()
	if jobContext.Err() == context.DeadlineExceeded {
		return string(output.data), fmt.Errorf("job %q exceeded its %d minute timeout", job.ID, job.TimeoutMinutes)
	}
	if err != nil {
		return string(output.data), fmt.Errorf("job %q worker failed: %w", job.ID, err)
	}
	return string(output.data), nil
}

func stepScript(steps []Step) string {
	var script strings.Builder
	for _, step := range steps {
		fmt.Fprintf(&script, "printf '\\n== %s ==\\n'\n%s\n", shellSingleQuote(step.Name), step.Run)
	}
	return script.String()
}

func shellSingleQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
}

func collectArtifacts(workspace, runRoot string, job Job) ([]ArtifactRecord, error) {
	var records []ArtifactRecord
	for _, path := range job.Artifacts {
		fullPath := filepath.Join(workspace, filepath.FromSlash(path))
		file, err := openRegularWorkspaceFile(workspace, path)
		if err != nil {
			return nil, fmt.Errorf("job %q artifact %q: %w", job.ID, path, err)
		}
		checksum := sha256.New()
		bytesWritten, copyErr := io.Copy(checksum, file)
		closeErr := file.Close()
		if copyErr != nil {
			return nil, fmt.Errorf("hash artifact %q: %w", path, copyErr)
		}
		if closeErr != nil {
			return nil, fmt.Errorf("close artifact %q: %w", path, closeErr)
		}
		storedPath := filepath.Join(runRoot, "artifacts", job.ID, filepath.FromSlash(path))
		if err := createPrivateDirectories(filepath.Dir(storedPath)); err != nil {
			return nil, fmt.Errorf("create artifact storage: %w", err)
		}
		if err := copyRegularFile(fullPath, storedPath); err != nil {
			return nil, fmt.Errorf("store artifact %q: %w", path, err)
		}
		records = append(records, ArtifactRecord{Path: path, SHA256: hex.EncodeToString(checksum.Sum(nil)), Bytes: bytesWritten, Stored: filepath.ToSlash(filepath.Join("artifacts", job.ID, filepath.FromSlash(path)))})
	}
	return records, nil
}

func openRegularWorkspaceFile(root, relative string) (*os.File, error) {
	if err := ValidateWorkspacePath(relative); err != nil {
		return nil, err
	}
	current := root
	parts := strings.Split(filepath.Clean(filepath.FromSlash(relative)), string(filepath.Separator))
	for index, part := range parts {
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err != nil {
			return nil, err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return nil, errors.New("symlinks are not accepted")
		}
		if index < len(parts)-1 && !info.IsDir() {
			return nil, errors.New("artifact path component is not a directory")
		}
		if index == len(parts)-1 && !info.Mode().IsRegular() {
			return nil, errors.New("artifact must be a regular file")
		}
	}
	return os.Open(current)
}

func copyRegularFile(source, destination string) error {
	input, err := os.Open(source)
	if err != nil {
		return err
	}
	defer input.Close()
	info, err := input.Stat()
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return errors.New("source is not a regular file")
	}
	output, err := os.OpenFile(destination, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(output, input)
	closeErr := output.Close()
	if copyErr != nil {
		return copyErr
	}
	return closeErr
}

func copyWorkspace(sourceRoot, targetRoot string) error {
	return filepath.WalkDir(sourceRoot, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(sourceRoot, path)
		if err != nil {
			return err
		}
		if relative == "." {
			return nil
		}
		if entry.IsDir() && (entry.Name() == ".git" || entry.Name() == ".pipeline") {
			return filepath.SkipDir
		}
		if relative == ".git" || relative == ".pipeline" {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("workspace contains unsupported symlink %q", relative)
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		destination := filepath.Join(targetRoot, relative)
		if info.IsDir() {
			return os.MkdirAll(destination, info.Mode().Perm()&0o755)
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("workspace contains unsupported file type %q", relative)
		}
		return copySourceFile(path, destination)
	})
}

func copySourceFile(source, destination string) error {
	input, err := os.Open(source)
	if err != nil {
		return err
	}
	defer input.Close()
	info, err := input.Stat()
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return errors.New("source is not a regular file")
	}
	mode := info.Mode().Perm()&0o755 | 0o400
	output, err := os.OpenFile(destination, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(output, input)
	closeErr := output.Close()
	if copyErr != nil {
		return copyErr
	}
	return closeErr
}

func createPrivateDirectories(path string) error {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return err
	}
	volume := filepath.VolumeName(absolute)
	current := volume + string(filepath.Separator)
	for _, part := range strings.Split(strings.TrimPrefix(absolute, current), string(filepath.Separator)) {
		if part == "" {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if errors.Is(err, os.ErrNotExist) {
			if err := os.Mkdir(current, 0o700); err != nil && !errors.Is(err, os.ErrExist) {
				return err
			}
			info, err = os.Lstat(current)
		}
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 || !info.IsDir() {
			return fmt.Errorf("run record path component %q is not a safe directory", current)
		}
	}
	return nil
}

func newRunID() (string, error) {
	var suffix [8]byte
	if _, err := rand.Read(suffix[:]); err != nil {
		return "", fmt.Errorf("generate run id: %w", err)
	}
	return time.Now().UTC().Format("20060102T150405") + "-" + hex.EncodeToString(suffix[:]), nil
}

func writeRecord(path string, record RunRecord) error {
	content, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return err
	}
	content = append(content, '\n')
	temporary := path + ".tmp"
	file, err := os.OpenFile(temporary, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	if _, err := file.Write(content); err != nil {
		file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}
