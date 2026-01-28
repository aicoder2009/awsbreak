package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"time"

	"github.com/aicoder2009/aws-hit-breaks/internal/models"
)

const (
	configDirName  = ".aws-hit-breaks"
	configFileName = "config.json"
	Version        = "1.0.0"
)

var (
	// iamRoleARNPattern validates IAM role ARN format
	iamRoleARNPattern = regexp.MustCompile(`^arn:aws:iam::\d{12}:role/[\w+=,.@-]+$`)

	// validRegions is a list of valid AWS regions
	validRegions = map[string]bool{
		"us-east-1": true, "us-east-2": true, "us-west-1": true, "us-west-2": true,
		"eu-west-1": true, "eu-west-2": true, "eu-west-3": true, "eu-central-1": true,
		"eu-north-1": true, "ap-southeast-1": true, "ap-southeast-2": true,
		"ap-northeast-1": true, "ap-northeast-2": true, "ap-south-1": true,
		"sa-east-1": true, "ca-central-1": true,
	}
)

// Manager handles configuration loading and saving
type Manager struct {
	configPath string
	config     *models.Config
}

// NewManager creates a new configuration manager
func NewManager() (*Manager, error) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get home directory: %w", err)
	}

	configDir := filepath.Join(homeDir, configDirName)
	configPath := filepath.Join(configDir, configFileName)

	return &Manager{
		configPath: configPath,
	}, nil
}

// GetConfigDir returns the configuration directory path
func (m *Manager) GetConfigDir() string {
	return filepath.Dir(m.configPath)
}

// Exists checks if configuration file exists
func (m *Manager) Exists() bool {
	_, err := os.Stat(m.configPath)
	return err == nil
}

// Load reads the configuration from disk
func (m *Manager) Load() (*models.Config, error) {
	data, err := os.ReadFile(m.configPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("configuration not found: run setup first")
		}
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var cfg models.Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	m.config = &cfg
	return &cfg, nil
}

// Save writes the configuration to disk
func (m *Manager) Save(cfg *models.Config) error {
	// Ensure config directory exists
	configDir := filepath.Dir(m.configPath)
	if err := os.MkdirAll(configDir, 0700); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	// Set metadata
	cfg.Version = Version
	if cfg.CreatedAt.IsZero() {
		cfg.CreatedAt = time.Now()
	}

	// Marshal to JSON with indentation
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	// Write atomically by writing to temp file first
	tmpPath := m.configPath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0600); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	if err := os.Rename(tmpPath, m.configPath); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("failed to save config: %w", err)
	}

	m.config = cfg
	return nil
}

// ValidateIAMRoleARN validates an IAM role ARN format
func ValidateIAMRoleARN(arn string) error {
	if !iamRoleARNPattern.MatchString(arn) {
		return fmt.Errorf("invalid IAM role ARN format: expected arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME")
	}
	return nil
}

// ValidateRegion validates an AWS region
func ValidateRegion(region string) error {
	if !validRegions[region] {
		return fmt.Errorf("invalid or unsupported region: %s", region)
	}
	return nil
}

// GetConfig returns the currently loaded config
func (m *Manager) GetConfig() *models.Config {
	return m.config
}

// GetDefaultRegion returns the default region from config or AWS_DEFAULT_REGION env
func (m *Manager) GetDefaultRegion() string {
	if m.config != nil && m.config.DefaultRegion != "" {
		return m.config.DefaultRegion
	}
	if region := os.Getenv("AWS_DEFAULT_REGION"); region != "" {
		return region
	}
	if region := os.Getenv("AWS_REGION"); region != "" {
		return region
	}
	return "us-east-1"
}
