# AWS Breaks 🚨 ⚠️

Emergency cost control for AWS accounts. Stop all services to save money without deleting anything.

## Installation

```bash
pip install aws-hit-breaks
```

## Quick Start

```bash
# First time setup (creates secure IAM role)
aws hit breaks

# Pause all services to save money
aws hit breaks

# Resume services
aws hit breaks --resume

# See what would happen (safe mode)
aws hit breaks --dry-run
```

## Features

- 🛡️ **Secure**: Uses dedicated IAM role with minimal permissions
- 🎯 **Simple**: Just run `aws hit breaks` - no complex options
- 💰 **Cost Savings**: Shows estimated monthly savings
- 🔄 **Reversible**: Resume everything exactly as it was
- 🔍 **Safe**: Dry-run mode to preview changes

## Supported Services

- EC2 instances (stop/start)
- RDS databases (stop/start) 
- ECS services (scale to zero/restore)
- Auto Scaling Groups (suspend/resume)
- Lambda provisioned concurrency (remove/restore)

## Security

AWS Hit Breaks requires you to create a dedicated IAM role with minimal required permissions. The tool provides a CloudFormation template for easy setup.

## License

MIT License - see LICENSE file for details.
