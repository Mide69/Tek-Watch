variable "name_prefix" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "alb_target_group_arn" { type = string }
variable "api_image_uri" { type = string }
variable "consumer_image_uri" { type = string }
variable "api_cpu" { type = number }
variable "api_memory" { type = number }
variable "api_desired_count" { type = number }
variable "consumer_cpu" { type = number }
variable "consumer_memory" { type = number }
variable "consumer_desired_count" { type = number }
variable "secrets_manager_arn" { type = string }
variable "sqs_ingest_queue_arn" { type = string }
variable "sqs_dlq_arn" { type = string }
variable "dynamodb_table_arns" { type = list(string) }

# ── Agent (self-hosted — dogfoods Tek Watch's own AWS account) ────────────────
variable "agent_image_uri" { type = string }
variable "agent_cpu" { type = number }
variable "agent_memory" { type = number }

variable "agent_schedule_expression" {
  type    = string
  default = "rate(5 minutes)"
}

# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = var.name_prefix

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = var.name_prefix }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ── CloudWatch Log Groups ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name_prefix}/api"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-api-logs" }
}

resource "aws_cloudwatch_log_group" "consumer" {
  name              = "/ecs/${var.name_prefix}/ingest-consumer"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-consumer-logs" }
}

# ── IAM — Task Execution Role (shared) ───────────────────────────────────────

resource "aws_iam_role" "execution" {
  name = "${var.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.secrets_manager_arn]
    }]
  })
}

# ── IAM — API Task Role ───────────────────────────────────────────────────────

resource "aws_iam_role" "api_task" {
  name = "${var.name_prefix}-api-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api_task" {
  name = "api-permissions"
  role = aws_iam_role.api_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_manager_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = var.dynamodb_table_arns
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:AdminGetUser", "cognito-idp:ListUsers"]
        Resource = ["*"]
      }
    ]
  })
}

# ── IAM — Consumer Task Role ──────────────────────────────────────────────────

resource "aws_iam_role" "consumer_task" {
  name = "${var.name_prefix}-consumer-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "consumer_task" {
  name = "consumer-permissions"
  role = aws_iam_role.consumer_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_manager_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage", "sqs:DeleteMessage",
          "sqs:DeleteMessageBatch", "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [var.sqs_ingest_queue_arn, var.sqs_dlq_arn]
      },
      {
        Effect = "Allow"
        Action = [
          # GetItem/Query for the customer-lookup cache in processor.py;
          # PutItem/BatchWriteItem to write metric/event records (replaces
          # the old timestream:WriteRecords grant — Timestream for
          # LiveAnalytics closed to new customers 2025-06-20).
          "dynamodb:GetItem", "dynamodb:Query",
          "dynamodb:PutItem", "dynamodb:BatchWriteItem"
        ]
        Resource = var.dynamodb_table_arns
      }
    ]
  })
}

# ── Security Group — ECS Tasks ────────────────────────────────────────────────

resource "aws_security_group" "ecs_tasks" {
  name = "${var.name_prefix}-ecs-tasks"
  # AWS EC2 SecurityGroup descriptions reject non-ASCII characters (an
  # em-dash here caused a real InvalidParameterValue apply failure) — plain
  # hyphens only in this field.
  description = "ECS tasks - inbound from ALB only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
    description     = "API from ALB"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name_prefix}-ecs-tasks" }
}

# ── API Task Definition ───────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.api_image_uri
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "ENVIRONMENT", value = var.environment },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "SECRETS_MANAGER_SECRET_ARN", value = var.secrets_manager_arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = { Name = "${var.name_prefix}-api" }
}

# ── API Service ───────────────────────────────────────────────────────────────

resource "aws_ecs_service" "api" {
  name                              = "api"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = var.api_desired_count
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 60
  force_new_deployment              = true

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = { Name = "${var.name_prefix}-api-service" }
}

# ── Ingest Consumer Task Definition ──────────────────────────────────────────

resource "aws_ecs_task_definition" "consumer" {
  family                   = "${var.name_prefix}-ingest-consumer"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.consumer_cpu
  memory                   = var.consumer_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.consumer_task.arn

  container_definitions = jsonencode([{
    name      = "ingest-consumer"
    image     = var.consumer_image_uri
    essential = true

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "ENVIRONMENT", value = var.environment },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "SECRETS_MANAGER_SECRET_ARN", value = var.secrets_manager_arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.consumer.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "consumer"
      }
    }
  }])

  tags = { Name = "${var.name_prefix}-ingest-consumer" }
}

# ── Ingest Consumer Service ───────────────────────────────────────────────────

resource "aws_ecs_service" "consumer" {
  name                 = "ingest-consumer"
  cluster              = aws_ecs_cluster.main.id
  task_definition      = aws_ecs_task_definition.consumer.arn
  desired_count        = var.consumer_desired_count
  launch_type          = "FARGATE"
  force_new_deployment = true

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = { Name = "${var.name_prefix}-consumer-service" }
}

# ── Auto Scaling — API ────────────────────────────────────────────────────────

resource "aws_appautoscaling_target" "api" {
  max_capacity       = 10
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name_prefix}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── Agent — scheduled Fargate task (NOT a long-running service) ──────────────
# agent/main.py runs its collectors once, publishes to SQS, and exits — see
# its own docstring: "7. Exit (ECS task completes)". An aws_ecs_service would
# just crash-loop relaunching a process that's designed to finish immediately.
# This mirrors the same EventBridge-scheduled-RunTask pattern used by the
# silence-detector Lambda (modules/monitoring/main.tf) and by the per-customer
# CloudFormation template (routers/admin/customers.py) — there, EventBridge
# isn't used because each customer account runs its own schedule via the CFN
# template's ScheduleExpression; here we need the equivalent for Tek Watch's
# own account.
#
# Image updates: the task definition references "${agent_image_uri}:latest"
# (mutable tag). Fargate pulls fresh on every RunTask invocation, so once
# agent.yml's build-and-push job re-pushes :latest, the *next* scheduled run
# automatically picks it up — no Terraform apply or ECS API call needed after
# a CI build. There is deliberately no aws_ecs_service or deploy step for this.

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/${var.name_prefix}/agent"
  retention_in_days = 30
  tags              = { Name = "${var.name_prefix}-agent-logs" }
}

resource "aws_iam_role" "agent_task" {
  name = "${var.name_prefix}-agent-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Same permission shape as the per-customer CFN template (read-only AWS
# visibility + permission to publish collected records back to our own
# ingest queue + Cost Explorer, which ReadOnlyAccess does not cover).
resource "aws_iam_role_policy_attachment" "agent_task_readonly" {
  role       = aws_iam_role.agent_task.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "agent_task" {
  name = "agent-permissions"
  role = aws_iam_role.agent_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:SendMessageBatch"]
        Resource = [var.sqs_ingest_queue_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ce:GetCostAndUsage", "ce:GetCostForecast"]
        Resource = ["*"] # Cost Explorer has no resource-level ARNs
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_manager_arn]
      }
    ]
  })
}

resource "aws_security_group" "agent_task" {
  name        = "${var.name_prefix}-agent-task"
  description = "Self-hosted agent task - outbound only, no inbound needed"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name_prefix}-agent-task" }
}

resource "aws_ecs_task_definition" "agent" {
  family                   = "${var.name_prefix}-agent"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_cpu
  memory                   = var.agent_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.agent_task.arn

  container_definitions = jsonencode([{
    name      = "agent"
    image     = "${var.agent_image_uri}:latest"
    essential = true

    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "ENVIRONMENT", value = var.environment },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "TEK_WATCH_CUSTOMER_ID", value = "TEK-WATCH-INTERNAL" },
      { name = "TEK_WATCH_INGEST_QUEUE_URL", value = var.sqs_ingest_queue_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "agent"
      }
    }
  }])

  tags = { Name = "${var.name_prefix}-agent" }
}

# ── EventBridge — invokes ecs:RunTask on a schedule ───────────────────────────

resource "aws_iam_role" "agent_scheduler" {
  name = "${var.name_prefix}-agent-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "agent_scheduler" {
  name = "run-agent-task"
  role = aws_iam_role.agent_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.agent.arn]
        Condition = {
          ArnEquals = { "ecs:cluster" = aws_ecs_cluster.main.arn }
        }
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.execution.arn,
          aws_iam_role.agent_task.arn,
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "agent_schedule" {
  name                = "${var.name_prefix}-agent-schedule"
  description         = "Run the self-hosted Tek Watch agent on a schedule"
  schedule_expression = var.agent_schedule_expression
}

resource "aws_cloudwatch_event_target" "agent" {
  rule      = aws_cloudwatch_event_rule.agent_schedule.name
  target_id = "agent-run-task"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.agent_scheduler.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.agent.arn
    task_count          = 1
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = var.private_subnet_ids
      security_groups  = [aws_security_group.agent_task.id]
      assign_public_ip = false
    }
  }
}

output "cluster_name" { value = aws_ecs_cluster.main.name }
output "api_service_name" { value = aws_ecs_service.api.name }
output "consumer_service_name" { value = aws_ecs_service.consumer.name }
output "agent_task_family" { value = aws_ecs_task_definition.agent.family }
