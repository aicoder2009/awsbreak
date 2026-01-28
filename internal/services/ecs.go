package services

import (
	"context"
	"fmt"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/ecs"
	"github.com/aws/aws-sdk-go-v2/service/ecs/types"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

// ECSServiceManager handles ECS service operations
type ECSServiceManager struct {
	client *ecs.Client
	region string
}

// NewECSServiceManager creates a new ECS service manager
func NewECSServiceManager(cfg aws.Config) *ECSServiceManager {
	return &ECSServiceManager{
		client: ecs.NewFromConfig(cfg),
		region: cfg.Region,
	}
}

// ServiceType returns the service type
func (m *ECSServiceManager) ServiceType() models.ServiceType {
	return models.ServiceECS
}

// Discover finds all running ECS services
func (m *ECSServiceManager) Discover(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	// List all clusters
	clusterArns, err := m.listClusters(ctx)
	if err != nil {
		return nil, err
	}

	// For each cluster, list and describe services
	for _, clusterArn := range clusterArns {
		services, err := m.discoverServicesInCluster(ctx, clusterArn, region)
		if err != nil {
			// Log error but continue with other clusters
			continue
		}
		resources = append(resources, services...)
	}

	return resources, nil
}

func (m *ECSServiceManager) listClusters(ctx context.Context) ([]string, error) {
	var clusterArns []string

	paginator := ecs.NewListClustersPaginator(m.client, &ecs.ListClustersInput{})
	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to list ECS clusters: %w", err)
		}
		clusterArns = append(clusterArns, output.ClusterArns...)
	}

	return clusterArns, nil
}

func (m *ECSServiceManager) discoverServicesInCluster(ctx context.Context, clusterArn, region string) ([]models.Resource, error) {
	var resources []models.Resource

	// List services in cluster
	var serviceArns []string
	paginator := ecs.NewListServicesPaginator(m.client, &ecs.ListServicesInput{
		Cluster: aws.String(clusterArn),
	})

	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to list ECS services: %w", err)
		}
		serviceArns = append(serviceArns, output.ServiceArns...)
	}

	if len(serviceArns) == 0 {
		return resources, nil
	}

	// Describe services (max 10 at a time)
	for i := 0; i < len(serviceArns); i += 10 {
		end := i + 10
		if end > len(serviceArns) {
			end = len(serviceArns)
		}

		batch := serviceArns[i:end]
		output, err := m.client.DescribeServices(ctx, &ecs.DescribeServicesInput{
			Cluster:  aws.String(clusterArn),
			Services: batch,
		})
		if err != nil {
			continue
		}

		for _, svc := range output.Services {
			// Only include services with running tasks
			if svc.DesiredCount > 0 || svc.RunningCount > 0 {
				resource := m.serviceToResource(svc, clusterArn, region)
				resources = append(resources, resource)
			}
		}
	}

	return resources, nil
}

// Pause scales an ECS service to zero
func (m *ECSServiceManager) Pause(ctx context.Context, resource models.Resource) error {
	clusterArn, ok := resource.Metadata["cluster_arn"].(string)
	if !ok {
		return fmt.Errorf("missing cluster_arn in resource metadata")
	}

	_, err := m.client.UpdateService(ctx, &ecs.UpdateServiceInput{
		Cluster:      aws.String(clusterArn),
		Service:      aws.String(resource.ResourceID),
		DesiredCount: aws.Int32(0),
	})
	if err != nil {
		return fmt.Errorf("failed to scale ECS service %s to zero: %w", resource.ResourceID, err)
	}

	return nil
}

// Resume restores an ECS service to its original task count
func (m *ECSServiceManager) Resume(ctx context.Context, resource models.Resource) error {
	clusterArn, ok := resource.Metadata["cluster_arn"].(string)
	if !ok {
		return fmt.Errorf("missing cluster_arn in resource metadata")
	}

	originalCount := int32(1) // Default
	if count, ok := resource.Metadata["original_desired_count"].(float64); ok {
		originalCount = int32(count)
	}

	_, err := m.client.UpdateService(ctx, &ecs.UpdateServiceInput{
		Cluster:      aws.String(clusterArn),
		Service:      aws.String(resource.ResourceID),
		DesiredCount: aws.Int32(originalCount),
	})
	if err != nil {
		return fmt.Errorf("failed to restore ECS service %s: %w", resource.ResourceID, err)
	}

	return nil
}

func (m *ECSServiceManager) serviceToResource(svc types.Service, clusterArn, region string) models.Resource {
	// Extract tags
	tags := make(map[string]string)
	for _, tag := range svc.Tags {
		if tag.Key != nil && tag.Value != nil {
			tags[*tag.Key] = *tag.Value
		}
	}

	metadata := map[string]any{
		"cluster_arn":            clusterArn,
		"original_desired_count": float64(svc.DesiredCount),
		"running_count":          svc.RunningCount,
		"launch_type":            string(svc.LaunchType),
	}

	if svc.TaskDefinition != nil {
		metadata["task_definition"] = *svc.TaskDefinition
	}

	return models.Resource{
		ServiceType:  models.ServiceECS,
		ResourceID:   aws.ToString(svc.ServiceName),
		Region:       region,
		CurrentState: models.StateRunning,
		Tags:         tags,
		Metadata:     metadata,
		CostPerHour:  0.05 * float64(svc.DesiredCount), // Rough estimate per task
	}
}
