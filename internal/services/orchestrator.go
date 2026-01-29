package services

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

const (
	// MaxConcurrentOperations limits concurrent AWS API calls to avoid rate limiting
	MaxConcurrentOperations = 5
	// MaxConcurrentDiscovery limits concurrent discovery operations
	MaxConcurrentDiscovery = 4
)

// Orchestrator coordinates operations across all service managers
type Orchestrator struct {
	awsCfg   aws.Config
	managers []ServiceManager
}

// NewOrchestrator creates a new orchestrator with all service managers
func NewOrchestrator(cfg aws.Config) *Orchestrator {
	return &Orchestrator{
		awsCfg: cfg,
		managers: []ServiceManager{
			NewEC2ServiceManager(cfg),
			NewRDSServiceManager(cfg),
			NewECSServiceManager(cfg),
			NewASGServiceManager(cfg),
		},
	}
}

// DiscoverAll discovers all resources across all service types
func (o *Orchestrator) DiscoverAll(ctx context.Context, region string) ([]models.Resource, error) {
	var (
		allResources []models.Resource
		mu           sync.Mutex
		wg           sync.WaitGroup
		errors       []error
	)

	// Semaphore to limit concurrent discovery operations
	sem := make(chan struct{}, MaxConcurrentDiscovery)

	for _, mgr := range o.managers {
		wg.Add(1)
		go func(m ServiceManager) {
			defer wg.Done()

			// Acquire semaphore
			sem <- struct{}{}
			defer func() { <-sem }()

			resources, err := m.Discover(ctx, region)
			mu.Lock()
			defer mu.Unlock()

			if err != nil {
				errors = append(errors, fmt.Errorf("%s discovery failed: %w", m.ServiceType(), err))
				return
			}
			allResources = append(allResources, resources...)
		}(mgr)
	}

	wg.Wait()

	// Return resources even if some discoveries failed
	if len(errors) > 0 && len(allResources) == 0 {
		return nil, fmt.Errorf("all discoveries failed: %v", errors)
	}

	return allResources, nil
}

// PauseAll pauses all given resources
func (o *Orchestrator) PauseAll(ctx context.Context, resources []models.Resource) ([]models.OperationResult, error) {
	return o.executeOperation(ctx, resources, "pause")
}

// ResumeAll resumes all given resources
func (o *Orchestrator) ResumeAll(ctx context.Context, resources []models.Resource) ([]models.OperationResult, error) {
	return o.executeOperation(ctx, resources, "resume")
}

func (o *Orchestrator) executeOperation(ctx context.Context, resources []models.Resource, operation string) ([]models.OperationResult, error) {
	var (
		results []models.OperationResult
		mu      sync.Mutex
		wg      sync.WaitGroup
	)

	// Semaphore to limit concurrent operations and avoid AWS rate limiting
	sem := make(chan struct{}, MaxConcurrentOperations)

	for _, resource := range resources {
		wg.Add(1)
		go func(r models.Resource) {
			defer wg.Done()

			// Acquire semaphore
			sem <- struct{}{}
			defer func() { <-sem }()

			start := time.Now()
			result := models.OperationResult{
				Resource:  r,
				Operation: operation,
				Timestamp: start,
			}

			// Find the appropriate manager
			mgr := o.getManager(r.ServiceType)
			if mgr == nil {
				result.Success = false
				result.Error = fmt.Sprintf("no manager for service type: %s", r.ServiceType)
				result.Duration = time.Since(start)
				mu.Lock()
				results = append(results, result)
				mu.Unlock()
				return
			}

			// Execute the operation
			var err error
			if operation == "pause" {
				err = mgr.Pause(ctx, r)
			} else {
				err = mgr.Resume(ctx, r)
			}

			result.Duration = time.Since(start)
			if err != nil {
				result.Success = false
				result.Error = err.Error()
				result.Message = fmt.Sprintf("Failed to %s %s", operation, r.ResourceID)
			} else {
				result.Success = true
				result.Message = fmt.Sprintf("Successfully %sd %s", operation, r.ResourceID)
			}

			mu.Lock()
			results = append(results, result)
			mu.Unlock()
		}(resource)
	}

	wg.Wait()
	return results, nil
}

func (o *Orchestrator) getManager(serviceType models.ServiceType) ServiceManager {
	for _, mgr := range o.managers {
		if mgr.ServiceType() == serviceType {
			return mgr
		}
	}
	return nil
}

// GetServiceManager returns the service manager for a specific service type
func (o *Orchestrator) GetServiceManager(serviceType models.ServiceType) ServiceManager {
	return o.getManager(serviceType)
}
