package models

import (
	"time"
)

// ServiceType represents the type of AWS service
type ServiceType string

const (
	ServiceEC2         ServiceType = "ec2"
	ServiceRDS         ServiceType = "rds"
	ServiceECS         ServiceType = "ecs"
	ServiceAutoScaling ServiceType = "autoscaling"
)

// ResourceState represents the current state of a resource
type ResourceState string

const (
	StateRunning   ResourceState = "running"
	StateStopped   ResourceState = "stopped"
	StateAvailable ResourceState = "available"
	StatePaused    ResourceState = "paused"
)

// Resource represents an AWS resource that can be paused/resumed
type Resource struct {
	ServiceType  ServiceType       `json:"service_type"`
	ResourceID   string            `json:"resource_id"`
	Region       string            `json:"region"`
	CurrentState ResourceState     `json:"current_state"`
	Tags         map[string]string `json:"tags,omitempty"`
	Metadata     map[string]any    `json:"metadata,omitempty"`
	CostPerHour  float64           `json:"cost_per_hour,omitempty"`
}

// OperationResult captures the result of a pause/resume operation
type OperationResult struct {
	Success   bool          `json:"success"`
	Resource  Resource      `json:"resource"`
	Operation string        `json:"operation"` // "pause", "resume", "discover"
	Message   string        `json:"message"`
	Timestamp time.Time     `json:"timestamp"`
	Duration  time.Duration `json:"duration,omitempty"`
	Error     string        `json:"error,omitempty"`
}

// AccountSnapshot stores the state of all resources before a pause operation
type AccountSnapshot struct {
	SnapshotID            string            `json:"snapshot_id"`
	Timestamp             time.Time         `json:"timestamp"`
	Region                string            `json:"region"`
	Resources             []Resource        `json:"resources"`
	OriginalStates        map[string]any    `json:"original_states"` // resource_id -> original config
	OperationResults      []OperationResult `json:"operation_results,omitempty"`
	TotalEstimatedSavings float64           `json:"total_estimated_savings"`
}

// Config stores the application configuration
type Config struct {
	IAMRoleARN    string    `json:"iam_role_arn"`
	DefaultRegion string    `json:"default_region"`
	CreatedAt     time.Time `json:"created_at"`
	Version       string    `json:"version"`
}

// CostReport summarizes cost savings
type CostReport struct {
	Resources       []Resource `json:"resources"`
	HourlySavings   float64    `json:"hourly_savings"`
	DailySavings    float64    `json:"daily_savings"`
	MonthlySavings  float64    `json:"monthly_savings"`
	GeneratedAt     time.Time  `json:"generated_at"`
}
