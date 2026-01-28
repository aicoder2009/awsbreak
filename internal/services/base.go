package services

import (
	"context"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

// ServiceManager defines the interface for AWS service managers
type ServiceManager interface {
	// ServiceType returns the type of service this manager handles
	ServiceType() models.ServiceType

	// Discover finds all resources of this service type in the given region
	Discover(ctx context.Context, region string) ([]models.Resource, error)

	// Pause stops/pauses a resource
	Pause(ctx context.Context, resource models.Resource) error

	// Resume starts/resumes a resource
	Resume(ctx context.Context, resource models.Resource) error
}
