package cli

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

// Exit codes for different error types
const (
	ExitSuccess      = 0
	ExitGeneralError = 1
	ExitConfigError  = 2
	ExitAuthError    = 3
	ExitServiceError = 4
)

var (
	// Flags
	flagGo      bool
	flagDryRun  bool
	flagRegion  string
	flagCheck   bool
	flagVersion bool

	// Version info
	version = "1.0.0"
)

// rootCmd represents the base command
var rootCmd = &cobra.Command{
	Use:   "awsbreak",
	Short: "Hit the brakes on your AWS spending",
	Long: `
    ___  _       _______ ____  ____  _____  ___   __ __
   /   || |     / / ___// __ )/ __ \/ ___/ /   | / //_/
  / /| || | /| / /\__ \/ __  / /_/ / __/  / /| |/ ,<
 / ___ || |/ |/ /___/ / /_/ / _, _/ /___ / ___ / /| |
/_/  |_||__/|__//____/_____/_/ |_/_____//_/  |_/_/ |_|

Emergency brake for your AWS account.
Stop all running services instantly. Resume anytime.

Examples:
  awsbreak                    Slam the brakes (pause all)
  awsbreak --go               Release brakes (resume all)
  awsbreak --check            Dashboard status
  awsbreak --dry-run          Preview only`,
	Run: runRoot,
}

func init() {
	rootCmd.Flags().BoolVarP(&flagGo, "go", "g", false, "Release brakes and resume services")
	rootCmd.Flags().BoolVarP(&flagDryRun, "dry-run", "d", false, "Preview without making changes")
	rootCmd.Flags().StringVar(&flagRegion, "region", "", "AWS region")
	rootCmd.Flags().BoolVarP(&flagCheck, "check", "c", false, "Dashboard status")
	rootCmd.Flags().BoolVarP(&flagVersion, "version", "v", false, "Show version")
}

// Execute runs the root command
func Execute() error {
	return rootCmd.Execute()
}

func runRoot(cmd *cobra.Command, args []string) {
	if flagVersion {
		fmt.Printf("awsbreak version %s\n", version)
		return
	}

	if flagCheck {
		runStatus()
		return
	}

	if flagGo {
		runResume()
		return
	}

	// Default: slam the brakes
	runPause()
}

func runPause() {
	fmt.Println("\n🛑 AWSBREAK - Slamming the brakes!")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	// Check configuration
	if !checkConfiguration() {
		runSetup()
		return
	}

	// Run interactive pause workflow
	interactivePause()
}

func runResume() {
	fmt.Println("\n🟢 AWSBREAK - Releasing the brakes!")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	if !checkConfiguration() {
		fmt.Println("❌ No configuration found. Run setup first.")
		os.Exit(ExitConfigError)
	}

	interactiveResume()
}

func runStatus() {
	fmt.Println("\n📊 AWSBREAK - Dashboard")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	showStatus()
}

func runSetup() {
	fmt.Println("\n🔧 First time? Let's get your brakes installed!")
	fmt.Println("   (Setting up secure IAM role access)")
	fmt.Println()

	interactiveSetup()
}
