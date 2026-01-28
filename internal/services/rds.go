package services

import (
	"context"
	"fmt"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/rds"
	"github.com/aws/aws-sdk-go-v2/service/rds/types"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

// RDSServiceManager handles RDS instance and cluster operations
type RDSServiceManager struct {
	client *rds.Client
	region string
}

// NewRDSServiceManager creates a new RDS service manager
func NewRDSServiceManager(cfg aws.Config) *RDSServiceManager {
	return &RDSServiceManager{
		client: rds.NewFromConfig(cfg),
		region: cfg.Region,
	}
}

// ServiceType returns the service type
func (m *RDSServiceManager) ServiceType() models.ServiceType {
	return models.ServiceRDS
}

// Discover finds all running RDS instances and Aurora clusters
func (m *RDSServiceManager) Discover(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	// Discover RDS instances
	instances, err := m.discoverInstances(ctx, region)
	if err != nil {
		return nil, err
	}
	resources = append(resources, instances...)

	// Discover Aurora clusters
	clusters, err := m.discoverClusters(ctx, region)
	if err != nil {
		return nil, err
	}
	resources = append(resources, clusters...)

	return resources, nil
}

func (m *RDSServiceManager) discoverInstances(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	paginator := rds.NewDescribeDBInstancesPaginator(m.client, &rds.DescribeDBInstancesInput{})
	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to describe RDS instances: %w", err)
		}

		for _, instance := range output.DBInstances {
			// Skip instances that are part of Aurora clusters (handled separately)
			if instance.DBClusterIdentifier != nil {
				continue
			}

			// Only include available (running) instances
			if aws.ToString(instance.DBInstanceStatus) != "available" {
				continue
			}

			resource := m.instanceToResource(instance, region)
			resources = append(resources, resource)
		}
	}

	return resources, nil
}

func (m *RDSServiceManager) discoverClusters(ctx context.Context, region string) ([]models.Resource, error) {
	var resources []models.Resource

	paginator := rds.NewDescribeDBClustersPaginator(m.client, &rds.DescribeDBClustersInput{})
	for paginator.HasMorePages() {
		output, err := paginator.NextPage(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to describe RDS clusters: %w", err)
		}

		for _, cluster := range output.DBClusters {
			// Only include available clusters
			if aws.ToString(cluster.Status) != "available" {
				continue
			}

			resource := m.clusterToResource(cluster, region)
			resources = append(resources, resource)
		}
	}

	return resources, nil
}

// Pause stops an RDS instance or cluster
func (m *RDSServiceManager) Pause(ctx context.Context, resource models.Resource) error {
	isCluster := resource.Metadata["is_cluster"] == true

	if isCluster {
		_, err := m.client.StopDBCluster(ctx, &rds.StopDBClusterInput{
			DBClusterIdentifier: aws.String(resource.ResourceID),
		})
		if err != nil {
			return fmt.Errorf("failed to stop RDS cluster %s: %w", resource.ResourceID, err)
		}
	} else {
		_, err := m.client.StopDBInstance(ctx, &rds.StopDBInstanceInput{
			DBInstanceIdentifier: aws.String(resource.ResourceID),
		})
		if err != nil {
			return fmt.Errorf("failed to stop RDS instance %s: %w", resource.ResourceID, err)
		}
	}

	return nil
}

// Resume starts an RDS instance or cluster
func (m *RDSServiceManager) Resume(ctx context.Context, resource models.Resource) error {
	isCluster := resource.Metadata["is_cluster"] == true

	if isCluster {
		_, err := m.client.StartDBCluster(ctx, &rds.StartDBClusterInput{
			DBClusterIdentifier: aws.String(resource.ResourceID),
		})
		if err != nil {
			return fmt.Errorf("failed to start RDS cluster %s: %w", resource.ResourceID, err)
		}
	} else {
		_, err := m.client.StartDBInstance(ctx, &rds.StartDBInstanceInput{
			DBInstanceIdentifier: aws.String(resource.ResourceID),
		})
		if err != nil {
			return fmt.Errorf("failed to start RDS instance %s: %w", resource.ResourceID, err)
		}
	}

	return nil
}

func (m *RDSServiceManager) instanceToResource(instance types.DBInstance, region string) models.Resource {
	// Extract tags
	tags := make(map[string]string)
	for _, tag := range instance.TagList {
		if tag.Key != nil && tag.Value != nil {
			tags[*tag.Key] = *tag.Value
		}
	}

	metadata := map[string]any{
		"is_cluster":     false,
		"engine":         aws.ToString(instance.Engine),
		"engine_version": aws.ToString(instance.EngineVersion),
		"instance_class": aws.ToString(instance.DBInstanceClass),
		"multi_az":       instance.MultiAZ,
	}

	if instance.AllocatedStorage != nil {
		metadata["storage_gb"] = *instance.AllocatedStorage
	}

	costPerHour := estimateRDSCost(aws.ToString(instance.DBInstanceClass), aws.ToString(instance.Engine), region)

	return models.Resource{
		ServiceType:  models.ServiceRDS,
		ResourceID:   aws.ToString(instance.DBInstanceIdentifier),
		Region:       region,
		CurrentState: models.StateAvailable,
		Tags:         tags,
		Metadata:     metadata,
		CostPerHour:  costPerHour,
	}
}

func (m *RDSServiceManager) clusterToResource(cluster types.DBCluster, region string) models.Resource {
	// Extract tags
	tags := make(map[string]string)
	for _, tag := range cluster.TagList {
		if tag.Key != nil && tag.Value != nil {
			tags[*tag.Key] = *tag.Value
		}
	}

	metadata := map[string]any{
		"is_cluster":     true,
		"engine":         aws.ToString(cluster.Engine),
		"engine_version": aws.ToString(cluster.EngineVersion),
	}

	if cluster.AllocatedStorage != nil {
		metadata["storage_gb"] = *cluster.AllocatedStorage
	}

	return models.Resource{
		ServiceType:  models.ServiceRDS,
		ResourceID:   aws.ToString(cluster.DBClusterIdentifier),
		Region:       region,
		CurrentState: models.StateAvailable,
		Tags:         tags,
		Metadata:     metadata,
		CostPerHour:  0.10, // Aurora cluster base cost
	}
}

func estimateRDSCost(instanceClass, engine, region string) float64 {
	// Simplified pricing
	pricing := map[string]float64{
		"db.t3.micro":  0.017,
		"db.t3.small":  0.034,
		"db.t3.medium": 0.068,
		"db.t3.large":  0.136,
		"db.m5.large":  0.171,
		"db.m5.xlarge": 0.342,
		"db.r5.large":  0.24,
		"db.r5.xlarge": 0.48,
	}

	if cost, ok := pricing[instanceClass]; ok {
		return cost
	}
	return 0.10 // Default estimate
}
