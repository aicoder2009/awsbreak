package main

import (
	"os"

	"github.com/aicoder2009/aws-hit-breaks/internal/cli"
)

func main() {
	if err := cli.Execute(); err != nil {
		os.Exit(1)
	}
}
