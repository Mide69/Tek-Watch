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
variable "timestream_database_arn" { type = string }
variable "timestream_table_arns" { type = list(string) }

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
        Effect = "Allow"
        Action = [
          "timestream:Select", "timestream:DescribeTable",
          "timestream:ListMeasures", "timestream:DescribeDatabase"
        ]
        Resource = concat([var.timestream_database_arn], var.timestream_table_arns)
      },
      {
        Effect   = "Allow"
        Action   = ["timestream:DescribeEndpoints"]
        Resource = ["*"]
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
          "dynamodb:GetItem", "dynamodb:Query"
        ]
        Resource = var.dynamodb_table_arns
      },
      {
        Effect = "Allow"
        Action = [
          "timestream:WriteRecords", "timestream:DescribeTable",
          "timestream:DescribeDatabase"
        ]
        Resource = concat([var.timestream_database_arn], var.timestream_table_arns)
      },
      {
        Effect   = "Allow"
        Action   = ["timestream:DescribeEndpoints"]
        Resource = ["*"]
      }
    ]
  })
}

# ── Security Group — ECS Tasks ────────────────────────────────────────────────

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.name_prefix}-ecs-tasks"
  description = "ECS tasks — inbound from ALB only"
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

output "cluster_name" { value = aws_ecs_cluster.main.name }
output "api_service_name" { value = aws_ecs_service.api.name }
output "consumer_service_name" { value = aws_ecs_service.consumer.name }
