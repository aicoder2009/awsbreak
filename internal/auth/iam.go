package auth

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials/stscreds"
	"github.com/aws/aws-sdk-go-v2/service/sts"
)

const (
	// SessionDuration is the duration for assumed role sessions
	SessionDuration = 1 * time.Hour
	// SessionName is the name used for STS sessions
	SessionName = "aws-hit-breaks-session"
)

// IAMAuthenticator handles IAM role-based authentication
type IAMAuthenticator struct {
	roleARN    string
	region     string
	awsCfg     *aws.Config
	expiration time.Time
	mu         sync.RWMutex
}

// NewIAMAuthenticator creates a new IAM authenticator
func NewIAMAuthenticator(roleARN, region string) *IAMAuthenticator {
	return &IAMAuthenticator{
		roleARN: roleARN,
		region:  region,
	}
}

// GetAWSConfig returns an AWS config with assumed role credentials
func (a *IAMAuthenticator) GetAWSConfig(ctx context.Context) (aws.Config, error) {
	a.mu.RLock()
	if a.awsCfg != nil && time.Now().Before(a.expiration) {
		cfg := *a.awsCfg
		a.mu.RUnlock()
		return cfg, nil
	}
	a.mu.RUnlock()

	return a.refreshCredentials(ctx)
}

// refreshCredentials assumes the IAM role and caches the credentials
func (a *IAMAuthenticator) refreshCredentials(ctx context.Context) (aws.Config, error) {
	a.mu.Lock()
	defer a.mu.Unlock()

	// Double-check in case another goroutine refreshed while we waited
	if a.awsCfg != nil && time.Now().Before(a.expiration) {
		return *a.awsCfg, nil
	}

	// Load default AWS config
	cfg, err := config.LoadDefaultConfig(ctx, config.WithRegion(a.region))
	if err != nil {
		return aws.Config{}, fmt.Errorf("failed to load AWS config: %w", err)
	}

	// If no role ARN specified, use default credentials
	if a.roleARN == "" {
		a.awsCfg = &cfg
		a.expiration = time.Now().Add(SessionDuration)
		return cfg, nil
	}

	// Create STS client to assume role
	stsClient := sts.NewFromConfig(cfg)

	// Create credentials provider that assumes the role
	creds := stscreds.NewAssumeRoleProvider(stsClient, a.roleARN, func(o *stscreds.AssumeRoleOptions) {
		o.RoleSessionName = SessionName
		o.Duration = SessionDuration
	})

	// Update config with assumed role credentials
	cfg.Credentials = aws.NewCredentialsCache(creds)

	// Verify credentials work by calling GetCallerIdentity
	if err := a.verifyCredentials(ctx, cfg); err != nil {
		return aws.Config{}, fmt.Errorf("failed to verify assumed role: %w", err)
	}

	a.awsCfg = &cfg
	a.expiration = time.Now().Add(SessionDuration - 5*time.Minute) // Refresh 5 min early

	return cfg, nil
}

// verifyCredentials checks that the credentials are valid
func (a *IAMAuthenticator) verifyCredentials(ctx context.Context, cfg aws.Config) error {
	stsClient := sts.NewFromConfig(cfg)
	_, err := stsClient.GetCallerIdentity(ctx, &sts.GetCallerIdentityInput{})
	if err != nil {
		return fmt.Errorf("credentials verification failed: %w", err)
	}
	return nil
}

// GetAWSConfigForRegion returns an AWS config for a specific region
func (a *IAMAuthenticator) GetAWSConfigForRegion(ctx context.Context, region string) (aws.Config, error) {
	cfg, err := a.GetAWSConfig(ctx)
	if err != nil {
		return aws.Config{}, err
	}
	cfg.Region = region
	return cfg, nil
}

// GetRoleARN returns the configured role ARN
func (a *IAMAuthenticator) GetRoleARN() string {
	return a.roleARN
}

// IsConfigured returns true if an IAM role is configured
func (a *IAMAuthenticator) IsConfigured() bool {
	return a.roleARN != ""
}

// CloudFormationTemplate returns the IAM role CloudFormation template
func CloudFormationTemplate() string {
	return `AWSTemplateFormatVersion: '2010-09-09'
Description: IAM Role for AWS Hit Breaks CLI

Resources:
  AWSHitBreaksRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: AWSHitBreaksRole
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
            Action: sts:AssumeRole
      Policies:
        - PolicyName: AWSHitBreaksPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  # EC2 permissions
                  - ec2:DescribeInstances
                  - ec2:StopInstances
                  - ec2:StartInstances
                  # RDS permissions
                  - rds:DescribeDBInstances
                  - rds:DescribeDBClusters
                  - rds:StopDBInstance
                  - rds:StartDBInstance
                  - rds:StopDBCluster
                  - rds:StartDBCluster
                  # ECS permissions
                  - ecs:DescribeServices
                  - ecs:DescribeClusters
                  - ecs:ListClusters
                  - ecs:ListServices
                  - ecs:UpdateService
                  # Auto Scaling permissions
                  - autoscaling:DescribeAutoScalingGroups
                  - autoscaling:SuspendProcesses
                  - autoscaling:ResumeProcesses
                  - autoscaling:SetDesiredCapacity
                  # Pricing permissions
                  - pricing:GetProducts
                Resource: '*'

Outputs:
  RoleARN:
    Description: ARN of the IAM role for AWS Hit Breaks
    Value: !GetAtt AWSHitBreaksRole.Arn
    Export:
      Name: AWSHitBreaksRoleARN
`
}
