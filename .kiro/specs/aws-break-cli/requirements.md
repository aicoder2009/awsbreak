# Requirements Document

## Introduction

AWS Break is a CLI tool that acts like a car's brakes for AWS accounts, allowing users to pause all running processes and services to stop incurring costs without permanently deleting resources. The tool provides a safety mechanism to quickly halt cost-generating activities across an entire AWS account.

## Glossary

- **AWS_Break_CLI**: The command-line interface tool for pausing AWS services
- **Pause_Operation**: The action of stopping or suspending AWS services without deletion
- **Resume_Operation**: The action of restarting previously paused AWS services
- **Cost_Generating_Service**: Any AWS service that incurs charges while running (EC2, RDS, Lambda, etc.)
- **Service_State**: The current operational status of an AWS service (running, stopped, paused)
- **Account_Snapshot**: A record of all service states before pause operations

## Requirements

### Requirement 1: Service Discovery and Inventory

**User Story:** As a DevOps engineer, I want to discover all running AWS services in my account, so that I can understand what resources are currently active and incurring costs.

#### Acceptance Criteria

1. WHEN the discovery command is executed, THE AWS_Break_CLI SHALL scan all AWS regions for active services
2. WHEN scanning regions, THE AWS_Break_CLI SHALL identify EC2 instances, RDS databases, Lambda functions, ECS services, and other cost-generating services
3. WHEN services are discovered, THE AWS_Break_CLI SHALL display service type, region, resource ID, and current state
4. WHEN discovery completes, THE AWS_Break_CLI SHALL provide a summary of total resources found by service type
5. THE AWS_Break_CLI SHALL save the discovered inventory to a local state file for reference

### Requirement 2: Pause All Services

**User Story:** As a cost-conscious AWS user, I want to pause all running services in my account, so that I can immediately stop incurring charges without losing my configurations.

#### Acceptance Criteria

1. WHEN the pause command is executed, THE AWS_Break_CLI SHALL stop all running EC2 instances across all regions
2. WHEN pausing services, THE AWS_Break_CLI SHALL stop RDS databases that support stopping
3. WHEN pausing services, THE AWS_Break_CLI SHALL disable auto-scaling groups to prevent new instances
4. WHEN pausing services, THE AWS_Break_CLI SHALL stop ECS services and scale them to zero tasks
5. WHEN each service is paused, THE AWS_Break_CLI SHALL record the original state in an Account_Snapshot
6. WHEN pause operations complete, THE AWS_Break_CLI SHALL provide a summary of all paused resources

### Requirement 3: Resume All Services

**User Story:** As a DevOps engineer, I want to resume all previously paused services, so that I can restore my AWS environment to its previous operational state.

#### Acceptance Criteria

1. WHEN the resume command is executed, THE AWS_Break_CLI SHALL read the Account_Snapshot to identify previously paused services
2. WHEN resuming services, THE AWS_Break_CLI SHALL start all previously running EC2 instances
3. WHEN resuming services, THE AWS_Break_CLI SHALL start all previously running RDS databases
4. WHEN resuming services, THE AWS_Break_CLI SHALL restore auto-scaling group configurations
5. WHEN resuming services, THE AWS_Break_CLI SHALL restore ECS services to their original task counts
6. WHEN resume operations complete, THE AWS_Break_CLI SHALL verify all services have returned to their original states

### Requirement 4: Selective Service Management

**User Story:** As a system administrator, I want to pause or resume specific types of services, so that I can have granular control over which resources are affected.

#### Acceptance Criteria

1. WHEN a service type filter is specified, THE AWS_Break_CLI SHALL only operate on services matching that type
2. WHEN region filters are specified, THE AWS_Break_CLI SHALL only operate on services in those regions
3. WHEN tag filters are specified, THE AWS_Break_CLI SHALL only operate on resources with matching tags
4. WHEN exclusion filters are specified, THE AWS_Break_CLI SHALL skip resources matching the exclusion criteria
5. THE AWS_Break_CLI SHALL validate filter parameters before executing operations

### Requirement 5: Safety and Confirmation

**User Story:** As a cautious AWS user, I want confirmation prompts and dry-run capabilities, so that I can verify operations before making changes to my infrastructure.

#### Acceptance Criteria

1. WHEN destructive operations are requested, THE AWS_Break_CLI SHALL prompt for user confirmation before proceeding
2. WHEN the dry-run flag is specified, THE AWS_Break_CLI SHALL show what would be changed without making actual changes
3. WHEN operations fail, THE AWS_Break_CLI SHALL provide clear error messages and suggested remediation steps
4. WHEN partial failures occur, THE AWS_Break_CLI SHALL continue with remaining operations and report all failures at the end
5. THE AWS_Break_CLI SHALL maintain detailed logs of all operations for troubleshooting

### Requirement 6: State Management and Recovery

**User Story:** As a reliability engineer, I want persistent state tracking and recovery capabilities, so that I can always restore my environment even if operations are interrupted.

#### Acceptance Criteria

1. WHEN pause operations begin, THE AWS_Break_CLI SHALL create a timestamped Account_Snapshot file
2. WHEN operations are interrupted, THE AWS_Break_CLI SHALL save partial progress to the state file
3. WHEN resume operations are requested, THE AWS_Break_CLI SHALL validate the Account_Snapshot exists and is readable
4. WHEN state files are corrupted, THE AWS_Break_CLI SHALL provide recovery options or manual intervention guidance
5. THE AWS_Break_CLI SHALL support multiple snapshots and allow users to specify which snapshot to restore from

### Requirement 7: Cost Estimation and Reporting

**User Story:** As a financial analyst, I want to see estimated cost savings from pause operations, so that I can quantify the financial impact of using the tool.

#### Acceptance Criteria

1. WHEN services are paused, THE AWS_Break_CLI SHALL estimate hourly cost savings based on instance types and regions
2. WHEN displaying summaries, THE AWS_Break_CLI SHALL show projected daily and monthly savings
3. WHEN operations complete, THE AWS_Break_CLI SHALL generate a report of all affected resources and their estimated costs
4. THE AWS_Break_CLI SHALL support exporting cost reports in JSON and CSV formats
5. WHEN cost data is unavailable, THE AWS_Break_CLI SHALL indicate which resources could not be estimated

### Requirement 8: IAM Role-Based Authentication

**User Story:** As a security-conscious user, I want the tool to use a dedicated IAM role with minimal permissions, so that I can maintain proper access controls and audit trails while keeping my account secure.

#### Acceptance Criteria

1. WHEN the tool is run for the first time, THE AWS_Break_CLI SHALL detect missing IAM role configuration and guide the user through setup
2. WHEN setting up authentication, THE AWS_Break_CLI SHALL provide a CloudFormation template with minimal required IAM permissions
3. WHEN the IAM role is configured, THE AWS_Break_CLI SHALL store the role ARN in a local configuration file
4. THE AWS_Break_CLI SHALL use STS assume role for all AWS API operations using the configured role
5. WHEN the IAM role is missing or invalid, THE AWS_Break_CLI SHALL provide clear guidance on role setup and required permissions

### Requirement 9: Simple Interactive Experience

**User Story:** As a busy developer, I want a simple command that guides me through the process, so that I can quickly pause my AWS costs without learning complex CLI options.

#### Acceptance Criteria

1. WHEN I run "aws hit breaks", THE AWS_Break_CLI SHALL automatically discover resources in my default region
2. WHEN resources are found, THE AWS_Break_CLI SHALL display them in a clear, readable format with estimated costs
3. WHEN displaying resources, THE AWS_Break_CLI SHALL show total monthly cost and potential savings
4. WHEN I confirm the pause operation, THE AWS_Break_CLI SHALL execute it and show progress
5. THE AWS_Break_CLI SHALL provide simple resume functionality with "aws hit breaks --resume"