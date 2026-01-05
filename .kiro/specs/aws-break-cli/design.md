# Design Document: AWS Break CLI

## Overview

AWS Break CLI is a Python-based command-line tool that provides emergency cost control for AWS accounts by pausing all running services without permanent deletion. The tool acts as a "brake pedal" for cloud spending, allowing users to quickly halt cost-generating activities and resume them later with full state preservation.

The design emphasizes safety, reliability, and comprehensive state management to ensure users can confidently pause their entire AWS infrastructure and restore it exactly as it was before.

## Architecture

The system follows a simple, user-friendly architecture focused on ease of use:

```
aws-hit-breaks/
├── cli/                    # Interactive command-line interface
├── auth/                   # IAM role setup and authentication
├── services/              # AWS service management (EC2, RDS, ECS)
├── state/                 # Simple state management
└── utils/                 # Cost estimation and helpers
```

### Core Components

1. **Interactive CLI**: Guides user through setup and operations with prompts
2. **IAM Role Manager**: Handles secure role-based authentication setup
3. **Service Discovery**: Automatically finds all cost-generating resources
4. **Pause/Resume Engine**: Safely stops and restarts AWS services
5. **Cost Calculator**: Shows estimated savings in real-time

### Installation and Setup

**Installation** (similar to Claude CLI):
```bash
pip install aws-hit-breaks
# or
brew install aws-hit-breaks
```

**First Run Setup**:
1. User runs `aws hit breaks`
2. Tool detects no IAM role configured
3. Provides IAM role CloudFormation template or manual setup instructions
4. User creates IAM role with required permissions
5. User provides role ARN to tool
6. Tool saves configuration locally
7. Ready to use!

## Components and Interfaces

### CLI Interface

The CLI provides a simple, interactive experience similar to Claude CLI:

```bash
# Primary command - interactive mode
aws hit breaks

# Optional direct commands for automation
aws hit breaks --pause [--dry-run]
aws hit breaks --resume [--dry-run]
aws hit breaks --status
```

**Interactive Flow**:
1. User runs `aws hit breaks`
2. Tool checks for IAM role configuration
3. If not configured, guides user through IAM role setup
4. Prompts for AWS region (defaults to current AWS CLI region)
5. Shows discovered resources and estimated costs
6. Asks user to confirm pause operation
7. Executes pause and shows savings summary

### Interactive User Experience

**First Time Setup**:
```
$ aws hit breaks

🚨 AWS Hit Breaks - Emergency Cost Control
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  No IAM role configured. Let's set this up securely.

I'll create an IAM role with minimal required permissions.
This ensures your AWS account stays secure.

Choose setup method:
1. 📋 Copy CloudFormation template (recommended)
2. 🔧 Manual IAM role creation

[1]: 
```

**Normal Operation**:
```
$ aws hit breaks

🚨 AWS Hit Breaks - Emergency Cost Control
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Scanning your AWS account...
   Region: us-east-1 (change with --region)
   
📊 Found running resources:
   • 3 EC2 instances (t3.medium, t3.large)
   • 1 RDS database (db.t3.micro)
   • 2 ECS services (5 total tasks)
   
💰 Estimated monthly cost: $847.20
💸 Potential monthly savings: $847.20

⚠️  This will PAUSE all resources above.
   They can be resumed later with 'aws hit breaks --resume'

Continue? [y/N]: 
```

### IAM Role Requirements

The tool requires a dedicated IAM role with specific permissions for security:

**Required IAM Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:StopInstances",
        "ec2:StartInstances",
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters", 
        "rds:StopDBInstance",
        "rds:StartDBInstance",
        "rds:StopDBCluster",
        "rds:StartDBCluster",
        "ecs:DescribeServices",
        "ecs:DescribeClusters",
        "ecs:UpdateService",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:SuspendProcesses",
        "autoscaling:ResumeProcesses",
        "autoscaling:SetDesiredCapacity",
        "lambda:ListFunctions",
        "lambda:GetProvisionedConcurrencyConfig",
        "lambda:PutProvisionedConcurrencyConfig",
        "lambda:DeleteProvisionedConcurrencyConfig",
        "pricing:GetProducts"
      ],
      "Resource": "*"
    }
  ]
}
```

**Setup Process**:
1. Tool provides CloudFormation template for easy IAM role creation
2. User deploys template in their AWS account
3. User copies the role ARN from CloudFormation outputs
4. Tool stores role ARN in local config file (`~/.aws-hit-breaks/config.json`)
5. All subsequent operations use this role via STS assume role

## Data Models

### Resource Model

```python
@dataclass
class Resource:
    service_type: str           # 'ec2', 'rds', 'ecs', etc.
    resource_id: str           # Instance ID, DB identifier, etc.
    region: str                # AWS region
    current_state: str         # Current operational state
    tags: Dict[str, str]       # Resource tags
    metadata: Dict[str, Any]   # Service-specific metadata
    cost_per_hour: Optional[float]  # Estimated hourly cost
```

### Operation Result Model

```python
@dataclass
class OperationResult:
    success: bool
    resource: Resource
    operation: str             # 'pause', 'resume', 'discover'
    message: str              # Success/error message
    timestamp: datetime
    duration: Optional[float]  # Operation duration in seconds
```

### Account Snapshot Model

```python
@dataclass
class AccountSnapshot:
    snapshot_id: str          # Unique identifier
    timestamp: datetime       # When snapshot was created
    resources: List[Resource] # All discovered resources
    original_states: Dict[str, Dict]  # Original configurations
    operation_results: List[OperationResult]  # Operation history
    total_estimated_savings: float  # Estimated cost savings
```

### Configuration File

Simple local configuration stored in `~/.aws-hit-breaks/config.json`:

```json
{
  "iam_role_arn": "arn:aws:iam::123456789012:role/AWSHitBreaksRole",
  "default_region": "us-east-1",
  "created_at": "2024-01-05T14:30:22Z",
  "version": "1.0.0"
}
```

### State File Format

Simplified state file stored in `~/.aws-hit-breaks/snapshots/`:

```json
{
  "snapshot_id": "pause-20240105-143022",
  "timestamp": "2024-01-05T14:30:22Z",
  "region": "us-east-1",
  "resources": [
    {
      "type": "ec2",
      "id": "i-1234567890abcdef0",
      "state": "running",
      "cost_per_hour": 0.0416
    },
    {
      "type": "rds",
      "id": "my-database",
      "state": "available",
      "cost_per_hour": 0.017
    }
  ],
  "total_monthly_savings": 847.20
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Complete Service Discovery
*For any* AWS account with resources across multiple regions, the discovery command should find all cost-generating services (EC2, RDS, ECS, ASG, Lambda) in all regions and include service type, region, resource ID, and current state in the output.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Discovery Summary Accuracy
*For any* discovery operation, the summary counts by service type should exactly match the number of resources actually discovered and displayed.
**Validates: Requirements 1.4**

### Property 3: State Persistence Round Trip
*For any* discovery or pause operation, the state file created should contain all discovered/affected resources, and reading the state file should reconstruct the exact same resource inventory.
**Validates: Requirements 1.5, 6.1**

### Property 4: Comprehensive Pause Operations
*For any* set of running AWS resources, the pause command should stop all EC2 instances, stop all stoppable RDS databases, scale all ECS services to zero tasks, and suspend all Auto Scaling Groups.
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 5: State Preservation During Pause
*For any* resource that is paused, the original state (running status, task counts, ASG configurations) should be recorded in the Account_Snapshot before any changes are made.
**Validates: Requirements 2.5**

### Property 6: Pause-Resume Round Trip
*For any* set of resources that are paused and then resumed, the final state should match the original state recorded in the Account_Snapshot (EC2 instances running, RDS databases started, ECS task counts restored, ASG configurations restored).
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

### Property 7: Filter Selectivity
*For any* operation with service type, region, tag, or exclusion filters specified, only resources matching the filter criteria should be affected, and all resources not matching should remain unchanged.
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 8: Filter Validation
*For any* invalid filter parameters (malformed tags, non-existent regions, invalid service types), the operation should be rejected with clear error messages before any AWS API calls are made.
**Validates: Requirements 4.5**

### Property 9: Dry Run Safety
*For any* operation executed with the dry-run flag, no actual changes should be made to AWS resources, but the output should show exactly what would be changed in a real execution.
**Validates: Requirements 5.2**

### Property 10: Partial Failure Resilience
*For any* operation where some resources fail to pause/resume, the operation should continue with remaining resources and provide a complete report of all successes and failures at the end.
**Validates: Requirements 5.4**

### Property 11: Cost Calculation Accuracy
*For any* paused resource with known pricing information, the estimated hourly cost savings should be calculated correctly based on the resource type, size, and region, and daily/monthly projections should be accurate multiples of the hourly rate.
**Validates: Requirements 7.1, 7.2**

### Property 12: Cost Report Completeness
*For any* completed pause operation, the cost report should include all affected resources and their estimated costs, and should be exportable in both JSON and CSV formats with identical data.
**Validates: Requirements 7.3, 7.4**

### Property 13: IAM Role Authentication
*For any* operation, the tool should use the configured IAM role via STS assume role, and when the role is missing or invalid, should provide clear setup guidance including CloudFormation template.
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

### Property 14: Interactive User Experience
*For any* execution of "aws hit breaks", the tool should automatically discover resources, display them with cost estimates, and allow the user to confirm before making changes.
**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

<function_calls>
<invoke name="prework">
<parameter name="featureName">aws-break-cli

## Error Handling

### Error Categories

**Authentication Errors**:
- Missing AWS credentials → Guide user to configure AWS CLI or environment variables
- Invalid credentials → Suggest credential refresh or profile verification
- Insufficient permissions → List specific IAM permissions required for each service

**Service Errors**:
- Service unavailable in region → Skip gracefully and report in summary
- Resource in transitional state → Wait with timeout or skip with warning
- API rate limiting → Implement exponential backoff with jitter

**State Management Errors**:
- Corrupted state file → Offer manual recovery options and backup restoration
- Missing state file for resume → Prevent resume operation and suggest discovery
- Concurrent operations → Use file locking to prevent state corruption

**Network and Infrastructure Errors**:
- Network connectivity issues → Retry with exponential backoff
- AWS service outages → Graceful degradation and clear error reporting
- Timeout errors → Configurable timeouts with reasonable defaults

### Error Recovery Strategies

1. **Graceful Degradation**: Continue operations on available services when others fail
2. **Atomic Operations**: Ensure state files are written atomically to prevent corruption
3. **Rollback Capability**: Provide manual rollback instructions when automated resume fails
4. **Detailed Logging**: Log all operations with sufficient detail for troubleshooting
5. **User Guidance**: Provide actionable error messages with specific remediation steps

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests**:
- Test specific examples and edge cases for each service manager
- Verify error handling for known failure scenarios
- Test CLI argument parsing and validation
- Test state file serialization/deserialization with specific examples
- Test cost calculation with known pricing data

**Property-Based Tests**:
- Verify universal properties across all inputs using Hypothesis (Python PBT library)
- Generate random AWS resource configurations to test discovery completeness
- Test pause-resume round trips with randomly generated resource states
- Verify filtering behavior with randomly generated filter combinations
- Test cost calculations with randomly generated resource configurations

### Property-Based Testing Configuration

- **Library**: Hypothesis for Python property-based testing
- **Iterations**: Minimum 100 iterations per property test
- **Test Tagging**: Each property test references its design document property
- **Tag Format**: **Feature: aws-break-cli, Property {number}: {property_text}**

### Testing Approach Balance

- **Unit tests focus on**: Specific examples, integration points, edge cases, error conditions
- **Property tests focus on**: Universal properties, comprehensive input coverage through randomization
- **Both are essential**: Unit tests catch concrete bugs, property tests verify general correctness

### Mock Strategy

- **AWS API Mocking**: Use moto library for comprehensive AWS service mocking
- **State File Testing**: Use temporary directories for isolated state file testing
- **Network Mocking**: Mock network failures and timeouts for resilience testing
- **Cost API Mocking**: Mock AWS Pricing API responses for cost calculation testing

### Integration Testing

- **End-to-End Scenarios**: Test complete discover-pause-resume workflows
- **Multi-Service Operations**: Verify coordination between different service managers
- **Error Propagation**: Test error handling across the entire operation pipeline
- **State Consistency**: Verify state file consistency across interrupted operations