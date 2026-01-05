# Implementation Plan: AWS Break CLI

## Overview

This implementation plan creates a Python-based CLI tool that provides emergency cost control for AWS accounts. The tool will be installable via pip and provide a simple interactive experience similar to the Claude CLI, with secure IAM role-based authentication.

## Tasks

- [x] 1. Set up Python project structure and dependencies
  - Create pyproject.toml with dependencies (boto3, click, rich, hypothesis)
  - Set up package structure with proper __init__.py files
  - Configure entry point for "aws-hit-breaks" command
  - _Requirements: 9.1_

- [x] 2. Implement core configuration and authentication system
  - [x] 2.1 Create configuration manager for local config file
    - Handle ~/.aws-hit-breaks/config.json creation and reading
    - Validate IAM role ARN format and storage
    - _Requirements: 8.3_

  - [x] 2.2 Write property test for configuration round trip
    - **Property 3: State Persistence Round Trip**
    - **Validates: Requirements 1.5, 6.1**

  - [x] 2.3 Implement IAM role authentication with STS
    - Create STS assume role functionality using boto3
    - Handle role assumption errors with clear messaging
    - _Requirements: 8.1, 8.4_

  - [x] 2.4 Write property test for IAM role authentication
    - **Property 13: IAM Role Authentication**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

- [x] 3. Create interactive CLI interface with Rich formatting
  - [x] 3.1 Implement main CLI command with Click framework
    - Create "aws hit breaks" main command entry point
    - Add --resume, --dry-run, --region flags
    - _Requirements: 9.1, 9.5_

  - [x] 3.2 Build interactive setup flow for first-time users
    - Detect missing IAM role configuration
    - Provide CloudFormation template for IAM role creation
    - Guide user through role ARN input and validation
    - _Requirements: 8.1, 8.2_

  - [x] 3.3 Write property test for interactive user experience
    - **Property 14: Interactive User Experience**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

- [x] 4. Implement AWS service discovery system
  - [x] 4.1 Create base service manager interface
    - Define abstract base class for all service managers
    - Implement common resource discovery patterns
    - _Requirements: 1.1, 1.2_

  - [x] 4.2 Implement EC2 service manager
    - Discover running EC2 instances across regions
    - Handle instance state checking and transitions
    - _Requirements: 1.2, 2.1, 3.2_

  - [x] 4.3 Implement RDS service manager
    - Discover running RDS instances and Aurora clusters
    - Handle database stop/start operations
    - _Requirements: 1.2, 2.2, 3.3_

  - [x] 4.4 Implement ECS service manager
    - Discover ECS services and current task counts
    - Handle service scaling to zero and restoration
    - _Requirements: 1.2, 2.4, 3.5_

  - [x] 4.5 Implement Auto Scaling Groups manager
    - Discover ASGs and their configurations
    - Handle process suspension and capacity management
    - _Requirements: 2.3, 3.4_

  - [x] 4.6 Write property test for complete service discovery
    - **Property 1: Complete Service Discovery**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 4.7 Write property test for discovery summary accuracy
    - **Property 2: Discovery Summary Accuracy**
    - **Validates: Requirements 1.4**

- [x] 5. Checkpoint - Ensure discovery system works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement pause and resume operations
  - [ ] 6.1 Create operation orchestrator for multi-service coordination
    - Coordinate pause/resume across all service types
    - Handle partial failures and error aggregation
    - _Requirements: 2.6, 5.4_

  - [ ] 6.2 Implement comprehensive pause functionality
    - Stop EC2 instances, RDS databases, scale ECS to zero
    - Suspend Auto Scaling Groups and save original states
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 6.3 Implement comprehensive resume functionality
    - Restore all services to their original states from snapshot
    - Verify successful restoration and report any issues
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ] 6.4 Write property test for comprehensive pause operations
    - **Property 4: Comprehensive Pause Operations**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [ ] 6.5 Write property test for state preservation during pause
    - **Property 5: State Preservation During Pause**
    - **Validates: Requirements 2.5**

  - [ ] 6.6 Write property test for pause-resume round trip
    - **Property 6: Pause-Resume Round Trip**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

- [ ] 7. Implement filtering and dry-run capabilities
  - [ ] 7.1 Create resource filtering system
    - Support service type, region, and tag-based filtering
    - Implement exclusion filters for selective operations
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ] 7.2 Implement dry-run mode
    - Show what would be changed without making actual changes
    - Provide detailed preview of all planned operations
    - _Requirements: 5.2_

  - [ ] 7.3 Write property test for filter selectivity
    - **Property 7: Filter Selectivity**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ] 7.4 Write property test for filter validation
    - **Property 8: Filter Validation**
    - **Validates: Requirements 4.5**

  - [ ] 7.5 Write property test for dry run safety
    - **Property 9: Dry Run Safety**
    - **Validates: Requirements 5.2**

- [ ] 8. Implement cost estimation and reporting
  - [ ] 8.1 Create cost calculator using AWS Pricing API
    - Fetch pricing data for EC2, RDS, ECS, and other services
    - Calculate hourly costs based on instance types and regions
    - _Requirements: 7.1_

  - [ ] 8.2 Implement cost reporting and export functionality
    - Generate detailed cost reports with savings estimates
    - Support JSON and CSV export formats
    - _Requirements: 7.2, 7.3, 7.4, 7.5_

  - [ ] 8.3 Write property test for cost calculation accuracy
    - **Property 11: Cost Calculation Accuracy**
    - **Validates: Requirements 7.1, 7.2**

  - [ ] 8.4 Write property test for cost report completeness
    - **Property 12: Cost Report Completeness**
    - **Validates: Requirements 7.3, 7.4**

- [ ] 9. Implement error handling and resilience
  - [ ] 9.1 Create comprehensive error handling system
    - Handle AWS API errors, network issues, and timeouts
    - Provide clear error messages with remediation guidance
    - _Requirements: 5.1, 5.3, 5.5_

  - [ ] 9.2 Implement partial failure resilience
    - Continue operations when some resources fail
    - Aggregate and report all failures at the end
    - _Requirements: 5.4_

  - [ ] 9.3 Write property test for partial failure resilience
    - **Property 10: Partial Failure Resilience**
    - **Validates: Requirements 5.4**

- [ ] 10. Implement state management and snapshots
  - [ ] 10.1 Create snapshot management system
    - Save and restore account snapshots with timestamps
    - Support multiple snapshots and snapshot selection
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [ ] 10.2 Implement state file corruption handling
    - Detect corrupted state files and provide recovery options
    - Offer manual intervention guidance when needed
    - _Requirements: 6.4_

- [ ] 11. Create packaging and installation setup
  - [ ] 11.1 Configure Python packaging with setuptools
    - Create proper package metadata and dependencies
    - Set up console script entry point for CLI command
    - Test installation via pip install

  - [ ] 11.2 Create CloudFormation template for IAM role
    - Provide ready-to-use CloudFormation template
    - Include minimal required permissions for all operations
    - Add clear deployment instructions

- [ ] 12. Final integration and testing
  - [ ] 12.1 Integration testing with mocked AWS services
    - Test complete discover-pause-resume workflows
    - Verify error handling across the entire pipeline
    - Test state consistency across interrupted operations

  - [ ] 12.2 Write integration tests for end-to-end scenarios
    - Test complete workflows from discovery to resume
    - Verify multi-service coordination and state management

- [ ] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive development from the start
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- The tool will be installable via `pip install aws-hit-breaks`
- All AWS operations use IAM role-based authentication for security