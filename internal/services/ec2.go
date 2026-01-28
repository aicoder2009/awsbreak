package services

import (
	"context"
	"fmt"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/ec2"
	"github.com/aws/aws-sdk-go-v2/service/ec2/types"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

// EC2ServiceManager handles EC2 instance operations
type EC2ServiceManager struct {
	client *ec2.Client
	region string
}

// NewEC2ServiceManager creates a new EC2 service manager
func NewEC2ServiceManager(cfg aws.Config) *EC2ServiceManager {
	return &EC2ServiceManager{
		client: ec2.NewFromConfig(cfg),
		region: cfg.Region,
	}
}

// ServiceType returns the service type
func (m *EC2ServiceManager) ServiceType() models.ServiceType {
	return models.ServiceEC2
}

// Discover finds all running EC2 instances
func (m *EC2ServiceManager) Discover(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	// Only filter for running instances
	input := &ec2.DescribeInstancesInput{
		Filters: []types.Filter{
			{
				Name:   aws.String("instance-state-name"),
				Values: []string{"running"},
			},
		},
	}

	paginator := ec2.NewDescribeInstancesPaginator(m.client, input)
	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to describe EC2 instances: %w", err)
		}

		for _, reservation := range output.Reservations {
			for _, instance := range reservation.Instances {
				resource := m.instanceToResource(instance, region)
				resources = append(resources, resource)
			}
		}
	}

	return resources, nil
}

// Pause stops an EC2 instance
func (m *EC2ServiceManager) Pause(ctx context.Context, resource models.Resource) error {
	input := &ec2.StopInstancesInput{
		InstanceIds: []string{resource.ResourceID},
	}

	_, err := m.client.StopInstances(ctx, input)
	if err != nil {
		return fmt.Errorf("failed to stop EC2 instance %s: %w", resource.ResourceID, err)
	}

	return nil
}

// Resume starts an EC2 instance
func (m *EC2ServiceManager) Resume(ctx context.Context, resource models.Resource) error {
	input := &ec2.StartInstancesInput{
		InstanceIds: []string{resource.ResourceID},
	}

	_, err := m.client.StartInstances(ctx, input)
	if err != nil {
		return fmt.Errorf("failed to start EC2 instance %s: %w", resource.ResourceID, err)
	}

	return nil
}

func (m *EC2ServiceManager) instanceToResource(instance types.Instance, region string) models.Resource {
	// Extract tags
	tags := make(map[string]string)
	for _, tag := range instance.Tags {
		if tag.Key != nil && tag.Value != nil {
			tags[*tag.Key] = *tag.Value
		}
	}

	// Extract metadata
	metadata := map[string]any{
		"instance_type":     string(instance.InstanceType),
		"availability_zone": aws.ToString(instance.Placement.AvailabilityZone),
	}

	if instance.VpcId != nil {
		metadata["vpc_id"] = *instance.VpcId
	}
	if instance.SubnetId != nil {
		metadata["subnet_id"] = *instance.SubnetId
	}
	if instance.PrivateIpAddress != nil {
		metadata["private_ip"] = *instance.PrivateIpAddress
	}
	if instance.PublicIpAddress != nil {
		metadata["public_ip"] = *instance.PublicIpAddress
	}

	// Get cost estimate
	costPerHour := estimateEC2Cost(string(instance.InstanceType), region)

	return models.Resource{
		ServiceType:  models.ServiceEC2,
		ResourceID:   aws.ToString(instance.InstanceId),
		Region:       region,
		CurrentState: models.StateRunning,
		Tags:         tags,
		Metadata:     metadata,
		CostPerHour:  costPerHour,
	}
}

// estimateEC2Cost returns estimated hourly cost for an EC2 instance type
func estimateEC2Cost(instanceType, region string) float64 {
	// Simplified pricing data - in production, use AWS Pricing API
	pricing := map[string]float64{
		"t2.micro":    0.0116,
		"t2.small":    0.023,
		"t2.medium":   0.0464,
		"t2.large":    0.0928,
		"t3.micro":    0.0104,
		"t3.small":    0.0208,
		"t3.medium":   0.0416,
		"t3.large":    0.0832,
		"m5.large":    0.096,
		"m5.xlarge":   0.192,
		"m5.2xlarge":  0.384,
		"c5.large":    0.085,
		"c5.xlarge":   0.17,
		"r5.large":    0.126,
		"r5.xlarge":   0.252,
	}

	if cost, ok := pricing[instanceType]; ok {
		return cost
	}
	return 0.05 // Default estimate
}
