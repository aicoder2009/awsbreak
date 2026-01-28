package cli

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/aicoder2009/aws-hit-breaks/internal/auth"
	"github.com/aicoder2009/aws-hit-breaks/internal/config"
	"github.com/aicoder2009/aws-hit-breaks/internal/models"
	"github.com/aicoder2009/aws-hit-breaks/internal/services"
)

var (
	configMgr *config.Manager
	authMgr   *auth.IAMAuthenticator
)

func checkConfiguration() bool {
	var err error
	configMgr, err = config.NewManager()
	if err != nil {
		return false
	}
	return configMgr.Exists()
}

func interactiveSetup() {
	fmt.Println("We need to install your brake system (IAM role).")
	fmt.Println("This gives awsbreak permission to stop/start your services.")
	fmt.Println()
	fmt.Println("How would you like to install?")
	fmt.Println("1. 🏎️  Quick install (CloudFormation - recommended)")
	fmt.Println("2. 🔧 Manual install (create IAM role yourself)")
	fmt.Println()

	choice := prompt("Enter choice [1]: ")
	if choice == "" {
		choice = "1"
	}

	switch choice {
	case "1":
		setupWithCloudFormation()
	case "2":
		setupManual()
	default:
		fmt.Println("Invalid choice. Using CloudFormation method.")
		setupWithCloudFormation()
	}
}

func setupWithCloudFormation() {
	fmt.Println()
	fmt.Println("📋 CloudFormation Template")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
	fmt.Println("1. Copy the template below")
	fmt.Println("2. Go to AWS Console > CloudFormation > Create Stack")
	fmt.Println("3. Paste the template and create the stack")
	fmt.Println("4. Copy the Role ARN from the Outputs tab")
	fmt.Println()
	fmt.Println("--- TEMPLATE START ---")
	fmt.Println(auth.CloudFormationTemplate())
	fmt.Println("--- TEMPLATE END ---")
	fmt.Println()

	completeSetup()
}

func setupManual() {
	fmt.Println()
	fmt.Println("🔧 Manual IAM Role Setup")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
	fmt.Println("Create an IAM role with these permissions:")
	fmt.Println("  - ec2:DescribeInstances, ec2:StopInstances, ec2:StartInstances")
	fmt.Println("  - rds:DescribeDBInstances, rds:StopDBInstance, rds:StartDBInstance")
	fmt.Println("  - ecs:DescribeServices, ecs:UpdateService")
	fmt.Println("  - autoscaling:DescribeAutoScalingGroups, autoscaling:SuspendProcesses")
	fmt.Println()

	completeSetup()
}

func completeSetup() {
	roleARN := prompt("Enter IAM Role ARN: ")
	if roleARN == "" {
		fmt.Println("❌ Role ARN is required")
		os.Exit(1)
	}

	// Validate ARN format
	if err := config.ValidateIAMRoleARN(roleARN); err != nil {
		fmt.Printf("❌ %v\n", err)
		os.Exit(1)
	}

	// Get default region
	region := prompt("Enter default AWS region [us-east-1]: ")
	if region == "" {
		region = "us-east-1"
	}

	if err := config.ValidateRegion(region); err != nil {
		fmt.Printf("❌ %v\n", err)
		os.Exit(1)
	}

	// Verify credentials work
	fmt.Println()
	fmt.Print("🔐 Verifying IAM role... ")

	authMgr = auth.NewIAMAuthenticator(roleARN, region)
	ctx := context.Background()
	_, err := authMgr.GetAWSConfig(ctx)
	if err != nil {
		fmt.Println("❌")
		fmt.Printf("   Failed to assume role: %v\n", err)
		fmt.Println("   Please check the role ARN and trust policy.")
		os.Exit(1)
	}
	fmt.Println("✅")

	// Save configuration
	cfg := &models.Config{
		IAMRoleARN:    roleARN,
		DefaultRegion: region,
	}

	if err := configMgr.Save(cfg); err != nil {
		fmt.Printf("❌ Failed to save configuration: %v\n", err)
		os.Exit(1)
	}

	fmt.Println()
	fmt.Println("✅ Brakes installed! Run 'awsbreak' to slam the brakes on your costs.")
}

func interactivePause() {
	ctx := context.Background()

	// Load configuration
	cfg, err := configMgr.Load()
	if err != nil {
		fmt.Printf("❌ %v\n", err)
		os.Exit(1)
	}

	// Determine region
	region := flagRegion
	if region == "" {
		region = configMgr.GetDefaultRegion()
	}

	fmt.Printf("\n🔍 Checking what's running in your AWS account...\n")
	fmt.Printf("   Region: %s (scanning for cost-burning resources)\n", region)

	// Initialize authenticator
	authMgr = auth.NewIAMAuthenticator(cfg.IAMRoleARN, region)
	awsCfg, err := authMgr.GetAWSConfig(ctx)
	if err != nil {
		fmt.Printf("❌ Authentication failed: %v\n", err)
		os.Exit(1)
	}

	// Create orchestrator and discover resources
	orchestrator := services.NewOrchestrator(awsCfg)
	resources, err := orchestrator.DiscoverAll(ctx, region)
	if err != nil {
		fmt.Printf("❌ Discovery failed: %v\n", err)
		os.Exit(1)
	}

	if len(resources) == 0 {
		fmt.Println("\n✅ All clear! No running resources burning money.")
		return
	}

	// Display discovered resources
	displayResources(resources)

	// Calculate costs
	totalMonthlyCost := calculateMonthlyCost(resources)

	fmt.Println()
	fmt.Printf("🔥 Burning: $%.2f/month\n", totalMonthlyCost)
	fmt.Printf("💰 You could save: $%.2f/month\n", totalMonthlyCost)
	fmt.Println()

	if flagDryRun {
		fmt.Println("👀 DRY RUN - Just checking mirrors, no brakes applied")
		return
	}

	fmt.Println("🛑 Ready to hit the brakes on all these resources?")
	fmt.Println("   (Resume anytime with 'awsbreak --resume')")
	fmt.Println()

	confirm := prompt("Continue? [y/N]: ")
	if !strings.HasPrefix(strings.ToLower(confirm), "y") {
		fmt.Println("Cancelled.")
		return
	}

	// Execute pause
	fmt.Println()
	fmt.Println("🛑 BRAKES ENGAGED - Stopping resources...")

	results, err := orchestrator.PauseAll(ctx, resources)
	if err != nil {
		fmt.Printf("❌ Brake failure: %v\n", err)
	}

	// Display results
	displayResults(results)

	fmt.Println()
	fmt.Printf("🏁 Done! Stopped %d resources. Saving ~$%.2f/month\n",
		countSuccessful(results), totalMonthlyCost)
	fmt.Println("   Run 'awsbreak --resume' when you're ready to go again.")
}

func interactiveResume() {
	ctx := context.Background()

	// Load configuration
	cfg, err := configMgr.Load()
	if err != nil {
		fmt.Printf("❌ %v\n", err)
		os.Exit(1)
	}

	region := flagRegion
	if region == "" {
		region = configMgr.GetDefaultRegion()
	}

	fmt.Printf("\n🟢 Releasing brakes in %s...\n", region)

	// Initialize authenticator
	authMgr = auth.NewIAMAuthenticator(cfg.IAMRoleARN, region)
	awsCfg, err := authMgr.GetAWSConfig(ctx)
	if err != nil {
		fmt.Printf("❌ Authentication failed: %v\n", err)
		os.Exit(1)
	}

	// Create orchestrator
	orchestrator := services.NewOrchestrator(awsCfg)

	// TODO: Load snapshot and resume from it
	// For now, just discover stopped resources
	resources, err := orchestrator.DiscoverAll(ctx, region)
	if err != nil {
		fmt.Printf("❌ Discovery failed: %v\n", err)
		os.Exit(1)
	}

	// Filter for stopped resources
	stoppedResources := filterStopped(resources)
	if len(stoppedResources) == 0 {
		fmt.Println("\n✅ Nothing parked - all services already running!")
		return
	}

	displayResources(stoppedResources)

	if flagDryRun {
		fmt.Println("\n👀 DRY RUN - Just checking, not starting anything")
		return
	}

	confirm := prompt("\nRelease brakes and start these? [y/N]: ")
	if !strings.HasPrefix(strings.ToLower(confirm), "y") {
		fmt.Println("Staying parked.")
		return
	}

	fmt.Println("\n🚀 Releasing brakes - starting resources...")
	results, err := orchestrator.ResumeAll(ctx, stoppedResources)
	if err != nil {
		fmt.Printf("❌ Engine trouble: %v\n", err)
	}

	displayResults(results)
	fmt.Printf("\n🏎️  Back on the road! Started %d resources.\n", countSuccessful(results))
}

func showStatus() {
	if configMgr == nil {
		var err error
		configMgr, err = config.NewManager()
		if err != nil {
			fmt.Printf("❌ %v\n", err)
			return
		}
	}

	if !configMgr.Exists() {
		fmt.Println("❌ Brakes not installed. Run 'awsbreak' to set up.")
		return
	}

	cfg, err := configMgr.Load()
	if err != nil {
		fmt.Printf("❌ %v\n", err)
		return
	}

	fmt.Println("🔧 Brake System Status")
	fmt.Println()
	fmt.Printf("   IAM Role:   %s\n", cfg.IAMRoleARN)
	fmt.Printf("   Region:     %s\n", cfg.DefaultRegion)
	fmt.Printf("   Version:    %s\n", cfg.Version)
	fmt.Printf("   Installed:  %s\n", cfg.CreatedAt.Format("2006-01-02 15:04:05"))
}

// Helper functions

func prompt(message string) string {
	fmt.Print(message)
	reader := bufio.NewReader(os.Stdin)
	input, _ := reader.ReadString('\n')
	return strings.TrimSpace(input)
}

func displayResources(resources []models.Resource) {
	fmt.Println()
	fmt.Println("📊 Found running resources:")

	// Group by service type
	byType := make(map[models.ServiceType][]models.Resource)
	for _, r := range resources {
		byType[r.ServiceType] = append(byType[r.ServiceType], r)
	}

	for svcType, items := range byType {
		fmt.Printf("   • %d %s\n", len(items), svcType)
		for _, r := range items {
			fmt.Printf("     - %s (%s)\n", r.ResourceID, r.CurrentState)
		}
	}
}

func displayResults(results []models.OperationResult) {
	successes := 0
	failures := 0

	for _, r := range results {
		if r.Success {
			successes++
			fmt.Printf("   ✅ %s %s\n", r.Resource.ServiceType, r.Resource.ResourceID)
		} else {
			failures++
			fmt.Printf("   ❌ %s %s: %s\n", r.Resource.ServiceType, r.Resource.ResourceID, r.Error)
		}
	}

	if failures > 0 {
		fmt.Printf("\n⚠️  %d succeeded, %d failed\n", successes, failures)
	}
}

func calculateMonthlyCost(resources []models.Resource) float64 {
	var total float64
	for _, r := range resources {
		total += r.CostPerHour * 24 * 30 // Approximate monthly hours
	}
	return total
}

func countSuccessful(results []models.OperationResult) int {
	count := 0
	for _, r := range results {
		if r.Success {
			count++
		}
	}
	return count
}

func filterStopped(resources []models.Resource) []models.Resource {
	var stopped []models.Resource
	for _, r := range resources {
		if r.CurrentState == models.StateStopped || r.CurrentState == models.StatePaused {
			stopped = append(stopped, r)
		}
	}
	return stopped
}
