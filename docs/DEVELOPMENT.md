# Tribe Watch - Development Guide

## Getting Started

### Prerequisites

- **Docker Desktop** (recommended) or Docker + Docker Compose
- **Python 3.12+** (for local development without Docker)
- **Node.js 18+** (for dashboard/admin portal development)
- **AWS CLI** configured with credentials
- **Git**

### Initial Setup

1. **Clone the repository**
```bash
git clone https://github.com/tektribe-ltd/tribe-watch.git
cd tribe-watch
```

2. **Copy environment template**
```bash
cp .env.example .env.local
```

3. **Edit .env.local** with your configuration
   - For local development, you can use placeholder values
   - LocalStack will emulate AWS services

### Running with Docker Compose (Recommended)

**Start all services:**
```bash
docker-compose up
```

**Start specific services:**
```bash
docker-compose up api ingest-consumer localstack
```

**Run agent manually:**
```bash
docker-compose --profile agent up agent
```

**View logs:**
```bash
docker-compose logs -f api
docker-compose logs -f ingest-consumer
```

**Stop all services:**
```bash
docker-compose down
```

**Rebuild after code changes:**
```bash
docker-compose up --build
```

### Running Services Individually

#### Agent

```bash
cd agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export TRIBE_WATCH_CUSTOMER_ID=TT-0001
export TRIBE_WATCH_INGEST_QUEUE_URL=https://sqs.eu-west-2.amazonaws.com/.../tribe-watch-ingest
export TRIBE_WATCH_API_KEY=your-api-key
export AWS_REGION=eu-west-2

python main.py
```

#### Ingest Consumer

```bash
cd ingest-consumer
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables (see .env.example)
python main.py
```

#### API

```bash
cd api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access API docs at: http://localhost:8000/docs

#### Dashboard (Not yet implemented)

```bash
cd dashboard
npm install
npm run dev
```

#### Admin Portal (Not yet implemented)

```bash
cd admin-portal
npm install
npm run dev
```

## Development Workflow

### Making Changes

1. **Create a feature branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**
   - Follow code style guidelines (see below)
   - Add tests for new functionality
   - Update documentation

3. **Test locally**
```bash
# Run tests
cd agent && pytest
cd api && pytest --cov=.

# Test with Docker Compose
docker-compose up --build
```

4. **Commit and push**
```bash
git add .
git commit -m "feat: add new feature"
git push origin feature/your-feature-name
```

5. **Create Pull Request**
   - Ensure CI passes
   - Request review from team

### Code Style Guidelines

#### Python

- **PEP 8** compliant
- **Line length:** Max 100 characters
- **Type hints:** Required on all function signatures
- **Docstrings:** Google style, required for all classes and public methods
- **Imports:** Organized (stdlib, third-party, local)
- **Logging:** Use `logging` module, never `print()`

**Example:**
```python
"""Module docstring."""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def process_data(items: List[str], limit: Optional[int] = None) -> List[str]:
    """Process a list of items.
    
    Args:
        items: List of strings to process.
        limit: Optional maximum number of items to process.
    
    Returns:
        Processed list of strings.
    """
    logger.info("Processing %d items", len(items))
    return items[:limit] if limit else items
```

#### TypeScript (Dashboard/Admin Portal)

- **Strict mode** enabled
- **No `any` types** - use `unknown` and narrow
- **Function components** only (no class components)
- **Absolute imports** using `@/` prefix
- **Tailwind CSS** for styling (no inline styles)

**Example:**
```typescript
import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface Props {
  title: string;
  onSubmit: (value: string) => void;
}

export function MyComponent({ title, onSubmit }: Props) {
  const [value, setValue] = useState('');
  
  return (
    <div>
      <h1>{title}</h1>
      <Button onClick={() => onSubmit(value)}>Submit</Button>
    </div>
  );
}
```

### Adding a New Collector

1. **Create collector file** in `agent/collectors/`
```python
"""Service collector — description."""
import logging
from typing import List
from botocore.exceptions import ClientError
from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class MyServiceCollector(BaseCollector):
    """Collects metrics from MyService."""
    
    SERVICE_NAME = "myservice"
    
    def collect(self) -> List[MetricRecord]:
        """Collect metrics."""
        records: List[MetricRecord] = []
        
        try:
            client = self._session.client("myservice", region_name=self._region)
            # Collection logic here
            
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "AccessDeniedException":
                logger.warning("MyService access denied in %s", self._region)
            else:
                logger.error("MyService collection failed: %s", exc)
        
        return records
```

2. **Import in main.py**
```python
from collectors.myservice import MyServiceCollector

REGIONAL_COLLECTORS = [
    # ... existing collectors
    MyServiceCollector,
]
```

3. **Test the collector**
```bash
cd agent
python main.py
```

### Adding a New API Endpoint

1. **Create or update router** in `api/routers/`
```python
"""My router — description."""
from fastapi import APIRouter, Depends
from auth.dependencies import CustomerContext, get_current_customer

router = APIRouter()


@router.get("/my-endpoint")
async def get_my_data(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get my data."""
    return {"data": "example"}
```

2. **Register router in main.py**
```python
from routers import myrouter

app.include_router(myrouter.router, prefix="/api/v1/myrouter", tags=["MyRouter"])
```

3. **Test the endpoint**
```bash
curl http://localhost:8000/api/v1/myrouter/my-endpoint \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Testing

### Running Tests

```bash
# Agent tests
cd agent
pytest -v

# API tests
cd api
pytest -v --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Writing Tests

**Example test:**
```python
import pytest
from mymodule import my_function


def test_my_function():
    """Test my_function with valid input."""
    result = my_function("input")
    assert result == "expected"


def test_my_function_error():
    """Test my_function with invalid input."""
    with pytest.raises(ValueError):
        my_function(None)
```

## Debugging

### Debugging with VS Code

**launch.json:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Agent",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/agent/main.py",
      "console": "integratedTerminal",
      "env": {
        "TRIBE_WATCH_CUSTOMER_ID": "TT-0001",
        "TRIBE_WATCH_INGEST_QUEUE_URL": "http://localhost:4566/...",
        "TRIBE_WATCH_API_KEY": "test-key"
      }
    },
    {
      "name": "Python: API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "cwd": "${workspaceFolder}/api"
    }
  ]
}
```

### Viewing Logs

**Docker Compose logs:**
```bash
docker-compose logs -f api
docker-compose logs -f ingest-consumer
docker-compose logs --tail=100 agent
```

**CloudWatch Logs (production):**
```bash
aws logs tail /ecs/tribe-watch-agent-TT-0001 --follow
aws logs tail /ecs/tribe-watch-api --follow
```

### Common Issues

**Issue: Agent can't connect to SQS**
- Check `TRIBE_WATCH_INGEST_QUEUE_URL` is correct
- Verify AWS credentials are configured
- Check IAM permissions

**Issue: API returns 401 Unauthorized**
- Verify JWT token is valid
- Check Cognito configuration
- Ensure token hasn't expired

**Issue: Timestream write fails**
- Check Timestream database and table exist
- Verify IAM permissions
- Check data format matches schema

## LocalStack Setup

LocalStack emulates AWS services for local development.

**Services available:**
- SQS
- DynamoDB
- Timestream (limited)
- Secrets Manager
- SNS
- SES
- Cognito (limited)

**Accessing LocalStack:**
```bash
# List SQS queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# List DynamoDB tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Create test queue
aws --endpoint-url=http://localhost:4566 sqs create-queue \
  --queue-name tribe-watch-ingest
```

## Useful Commands

```bash
# Format Python code
black agent/ api/ ingest-consumer/

# Lint Python code
flake8 agent/ api/ ingest-consumer/

# Type check Python code
mypy agent/ api/ ingest-consumer/

# Build Docker images
docker build -t tribe-watch-agent:latest ./agent
docker build -t tribe-watch-api:latest ./api

# Run agent once
docker run --rm \
  -e TRIBE_WATCH_CUSTOMER_ID=TT-0001 \
  -e TRIBE_WATCH_INGEST_QUEUE_URL=... \
  -e TRIBE_WATCH_API_KEY=... \
  tribe-watch-agent:latest

# Clean up Docker
docker-compose down -v
docker system prune -a
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Next.js Documentation](https://nextjs.org/docs)
- [AWS SDK Documentation](https://docs.aws.amazon.com/)
- [Anthropic Claude API](https://docs.anthropic.com/)

## Getting Help

- **Internal:** Slack #tribe-watch-dev
- **Issues:** GitHub Issues
- **Documentation:** See `.kiro/specs/` directory

---

Happy coding! 🚀
