package services

import (
	"context"
	"fmt"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/autoscaling"
	"github.com/aws/aws-sdk-go-v2/service/autoscaling/types"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

// ASGServiceManager handles Auto Scaling Group operations
type ASGServiceManager struct {
	client *autoscaling.Client
	region string
}

// NewASGServiceManager creates a new Auto Scaling Group service manager
func NewASGServiceManager(cfg aws.Config) *ASGServiceManager {
	return &ASGServiceManager{
		client: autoscaling.NewFromConfig(cfg),
		region: cfg.Region,
	}
}

// ServiceType returns the service type
func (m *ASGServiceManager) ServiceType() models.ServiceType {
	return models.ServiceAutoScaling
}

// Discover finds all Auto Scaling Groups with running instances
func (m *ASGServiceManager) Discover(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	paginator := autoscaling.NewDescribeAutoScalingGroupsPaginator(m.client, &autoscaling.DescribeAutoScalingGroupsInput{})
	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to describe Auto Scaling Groups: %w", err)
		}

		for _, asg := range output.AutoScalingGroups {
			// Only include ASGs with desired capacity > 0 or running instances
			if *asg.DesiredCapacity > 0 || len(asg.Instances) > 0 {
				resource := m.asgToResource(asg, region)
				resources = append(resources, resource)
			}
		}
	}

	return resources, nil
}

// Pause suspends Auto Scaling processes and scales to zero
func (m *ASGServiceManager) Pause(ctx context.Context, resource models.Resource) error {
	asgName := resource.ResourceID

	// Suspend all scaling processes
	_, err := m.client.SuspendProcesses(ctx, &autoscaling.SuspendProcessesInput{
		AutoScalingGroupName: aws.String(asgName),
		ScalingProcesses: []string{
			"Launch",
			"Terminate",
			"HealthCheck",
			"ReplaceUnhealthy",
			"AZRebalance",
			"AlarmNotification",
			"ScheduledActions",
			"AddToLoadBalancer",
		},
	})
	if err != nil {
		return fmt.Errorf("failed to suspend ASG processes for %s: %w", asgName, err)
	}

	// Scale to zero
	_, err = m.client.SetDesiredCapacity(ctx, &autoscaling.SetDesiredCapacityInput{
		AutoScalingGroupName: aws.String(asgName),
		DesiredCapacity:      aws.Int32(0),
	})
	if err != nil {
		return fmt.Errorf("failed to scale ASG %s to zero: %w", asgName, err)
	}

	return nil
}

// Resume restores Auto Scaling Group to its original state
func (m *ASGServiceManager) Resume(ctx context.Context, resource models.Resource) error {
	asgName := resource.ResourceID

	// Get original desired capacity
	originalCapacity := int32(1) // Default
	if cap, ok := resource.Metadata["original_desired_capacity"].(float64); ok {
		originalCapacity = int32(cap)
	}

	// Restore desired capacity
	_, err := m.client.SetDesiredCapacity(ctx, &autoscaling.SetDesiredCapacityInput{
		AutoScalingGroupName: aws.String(asgName),
		DesiredCapacity:      aws.Int32(originalCapacity),
	})
	if err != nil {
		return fmt.Errorf("failed to restore ASG %s capacity: %w", asgName, err)
	}

	// Resume all scaling processes
	_, err = m.client.ResumeProcesses(ctx, &autoscaling.ResumeProcessesInput{
		AutoScalingGroupName: aws.String(asgName),
		ScalingProcesses: []string{
			"Launch",
			"Terminate",
			"HealthCheck",
			"ReplaceUnhealthy",
			"AZRebalance",
			"AlarmNotification",
			"ScheduledActions",
			"AddToLoadBalancer",
		},
	})
	if err != nil {
		return fmt.Errorf("failed to resume ASG processes for %s: %w", asgName, err)
	}

	return nil
}

func (m *ASGServiceManager) asgToResource(asg types.AutoScalingGroup, region string) models.Resource {
	// Extract tags
	tags := make(map[string]string)
	for _, tag := range asg.Tags {
		if tag.Key != nil && tag.Value != nil {
			tags[*tag.Key] = *tag.Value
		}
	}

	// Get suspended processes
	suspendedProcesses := make([]string, 0, len(asg.SuspendedProcesses))
	for _, sp := range asg.SuspendedProcesses {
		if sp.ProcessName != nil {
			suspendedProcesses = append(suspendedProcesses, *sp.ProcessName)
		}
	}

	metadata := map[string]any{
		"original_desired_capacity": float64(*asg.DesiredCapacity),
		"min_size":                  *asg.MinSize,
		"max_size":                  *asg.MaxSize,
		"instance_count":            len(asg.Instances),
		"suspended_processes":       suspendedProcesses,
	}

	if asg.LaunchConfigurationName != nil {
		metadata["launch_configuration"] = *asg.LaunchConfigurationName
	}
	if asg.LaunchTemplate != nil && asg.LaunchTemplate.LaunchTemplateName != nil {
		metadata["launch_template"] = *asg.LaunchTemplate.LaunchTemplateName
	}

	// Estimate cost based on instance count
	instanceCount := len(asg.Instances)
	costPerHour := float64(instanceCount) * 0.05 // Rough estimate

	return models.Resource{
		ServiceType:  models.ServiceAutoScaling,
		ResourceID:   aws.ToString(asg.AutoScalingGroupName),
		Region:       region,
		CurrentState: models.StateRunning,
		Tags:         tags,
		Metadata:     metadata,
		CostPerHour:  costPerHour,
	}
}
