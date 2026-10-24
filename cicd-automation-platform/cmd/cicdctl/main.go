package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/Yamza786/it-portfolio/cicd-automation-platform/internal/pipeline"
)

func main() {
	if err := execute(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "cicdctl:", err)
		os.Exit(1)
	}
}

func execute(arguments []string) error {
	if len(arguments) < 1 || len(arguments) > 2 {
		return usage()
	}
	command := arguments[0]
	path := "pipeline.yaml"
	if len(arguments) == 2 {
		path = arguments[1]
	}
	definition, err := pipeline.Load(path)
	if err != nil {
		return err
	}
	switch command {
	case "validate":
		fmt.Printf("Pipeline %q is valid (%d jobs).\n", definition.Name, len(definition.Jobs))
	case "plan":
		fmt.Printf("Pipeline: %s\n", definition.Name)
		for index, job := range definition.Jobs {
			fmt.Printf("%02d  %-20s image=%s timeout=%dm", index+1, job.ID, job.Image, job.TimeoutMinutes)
			if len(job.Needs) > 0 {
				fmt.Printf(" needs=%v", job.Needs)
			}
			fmt.Printf(" steps=%d artifacts=%d\n", len(job.Steps), len(job.Artifacts))
		}
	case "run":
		record, err := pipeline.Run(definition, ".")
		if err != nil {
			encoded, encodeErr := json.MarshalIndent(record, "", "  ")
			if encodeErr == nil && len(encoded) > 0 {
				fmt.Fprintln(os.Stderr, string(encoded))
			}
			return err
		}
		encoded, err := json.MarshalIndent(record, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(encoded))
	default:
		return usage()
	}
	return nil
}

func usage() error {
	return fmt.Errorf("usage: cicdctl <validate|plan|run> [pipeline.yaml]")
}
