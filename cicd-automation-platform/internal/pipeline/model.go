package pipeline

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"gopkg.in/yaml.v3"
)

const maxConfigBytes = 1 << 20

var identifier = regexp.MustCompile(`^[a-z][a-z0-9-]{0,39}$`)
var imageReference = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/:@-]*$`)

type Definition struct {
	Name    string `yaml:"name" json:"name"`
	Version int    `yaml:"version" json:"version"`
	Jobs    []Job  `yaml:"jobs" json:"jobs"`
}

type Job struct {
	ID             string   `yaml:"id" json:"id"`
	Image          string   `yaml:"image" json:"image"`
	Needs          []string `yaml:"needs,omitempty" json:"needs,omitempty"`
	TimeoutMinutes int      `yaml:"timeout_minutes,omitempty" json:"timeout_minutes,omitempty"`
	Steps          []Step   `yaml:"steps" json:"steps"`
	Artifacts      []string `yaml:"artifacts,omitempty" json:"artifacts,omitempty"`
}

type Step struct {
	Name string `yaml:"name" json:"name"`
	Run  string `yaml:"run" json:"run"`
}

func Load(path string) (Definition, error) {
	file, err := os.Open(path)
	if err != nil {
		return Definition{}, fmt.Errorf("open pipeline: %w", err)
	}
	defer file.Close()
	content, err := io.ReadAll(io.LimitReader(file, maxConfigBytes+1))
	if err != nil {
		return Definition{}, fmt.Errorf("read pipeline: %w", err)
	}
	if len(content) > maxConfigBytes {
		return Definition{}, fmt.Errorf("pipeline exceeds %d bytes", maxConfigBytes)
	}
	var definition Definition
	decoder := yaml.NewDecoder(bytes.NewReader(content))
	decoder.KnownFields(true)
	if err := decoder.Decode(&definition); err != nil {
		return Definition{}, fmt.Errorf("parse pipeline YAML: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return Definition{}, errors.New("pipeline must contain one YAML document")
		}
		return Definition{}, fmt.Errorf("parse trailing YAML: %w", err)
	}
	if err := Validate(definition); err != nil {
		return Definition{}, err
	}
	return definition, nil
}

func Validate(definition Definition) error {
	if !identifier.MatchString(definition.Name) {
		return errors.New("name must be a lowercase identifier up to 40 characters")
	}
	if definition.Version != 1 {
		return errors.New("version must be 1")
	}
	if len(definition.Jobs) == 0 || len(definition.Jobs) > 32 {
		return errors.New("jobs must contain between 1 and 32 entries")
	}
	jobIndexes := make(map[string]int, len(definition.Jobs))
	for index := range definition.Jobs {
		job := &definition.Jobs[index]
		if !identifier.MatchString(job.ID) {
			return fmt.Errorf("job %d has invalid id", index+1)
		}
		if _, exists := jobIndexes[job.ID]; exists {
			return fmt.Errorf("duplicate job id %q", job.ID)
		}
		jobIndexes[job.ID] = index
		if !imageReference.MatchString(job.Image) || strings.HasSuffix(job.Image, ":latest") {
			return fmt.Errorf("job %q image must be a non-empty image reference and cannot use :latest", job.ID)
		}
		if job.TimeoutMinutes == 0 {
			job.TimeoutMinutes = 10
		}
		if job.TimeoutMinutes < 1 || job.TimeoutMinutes > 60 {
			return fmt.Errorf("job %q timeout_minutes must be between 1 and 60", job.ID)
		}
		if len(job.Steps) == 0 || len(job.Steps) > 32 {
			return fmt.Errorf("job %q steps must contain between 1 and 32 entries", job.ID)
		}
		for stepIndex, step := range job.Steps {
			if strings.TrimSpace(step.Name) == "" || len(step.Name) > 100 || strings.TrimSpace(step.Run) == "" || len(step.Run) > 16_384 {
				return fmt.Errorf("job %q step %d needs a short name and a run command", job.ID, stepIndex+1)
			}
		}
		seenNeeds := make(map[string]bool)
		for _, need := range job.Needs {
			needIndex, exists := jobIndexes[need]
			if !exists || needIndex >= index {
				return fmt.Errorf("job %q needs %q, which must be declared earlier", job.ID, need)
			}
			if seenNeeds[need] {
				return fmt.Errorf("job %q repeats dependency %q", job.ID, need)
			}
			seenNeeds[need] = true
		}
		seenArtifacts := make(map[string]bool)
		for _, artifact := range job.Artifacts {
			if err := ValidateWorkspacePath(artifact); err != nil {
				return fmt.Errorf("job %q artifact %q: %w", job.ID, artifact, err)
			}
			if seenArtifacts[artifact] {
				return fmt.Errorf("job %q repeats artifact %q", job.ID, artifact)
			}
			seenArtifacts[artifact] = true
		}
	}
	return nil
}

func ValidateWorkspacePath(path string) error {
	if path == "" || filepath.IsAbs(path) || strings.Contains(path, "\\") || strings.ContainsAny(path, "*?[]") {
		return errors.New("must be a relative, literal workspace path")
	}
	clean := filepath.Clean(path)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return errors.New("must stay inside the workspace")
	}
	return nil
}
