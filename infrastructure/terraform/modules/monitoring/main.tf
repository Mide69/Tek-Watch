variable "name_prefix"              { type = string }
variable "environment"              { type = string }
variable "aws_region"               { type = string }
variable "ecs_cluster_name"         { type = string }
variable "api_service_name"         { type = string }
variable "consumer_service_name"    { type = string }
variable "sqs_ingest_queue_name"    { type = string }
variable "sqs_dlq_name"             { type = string }
variable "dynamodb_customers_table" { type = string }

# ── SNS — Ops Alerts ──────────────────────────────────────────────────────────

resource "aws_sns_topic" "ops_alerts" {
  name = "${var.name_prefix}-ops-alerts"
  tags = { Name = "${var.name_prefix}-ops-alerts" }
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────

# DLQ depth > 0 — any failed ingest message is critical
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.name_prefix}-dlq-depth"
  alarm_description   = "Messages in ingest DLQ — validation failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = { QueueName = var.sqs_dlq_name }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]

  tags = { Name = "${var.name_prefix}-dlq-depth-alarm" }
}

# API error rate > 1%
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name_prefix}-api-5xx-rate"
  alarm_description   = "API 5xx error rate exceeds 1%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "errors / MAX([errors, requests]) * 100"
    label       = "5xx Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "HTTPCode_Target_5XX_Count"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
    }
  }

  metric_query {
    id = "requests"
    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 60
      stat        = "Sum"
    }
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = { Name = "${var.name_prefix}-api-5xx-alarm" }
}

# API ECS task count drops to 0
resource "aws_cloudwatch_metric_alarm" "api_task_count" {
  alarm_name          = "${var.name_prefix}-api-task-count"
  alarm_description   = "API ECS service has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = { Name = "${var.name_prefix}-api-task-count-alarm" }
}

# Consumer ECS task count drops to 0
resource "aws_cloudwatch_metric_alarm" "consumer_task_count" {
  alarm_name          = "${var.name_prefix}-consumer-task-count"
  alarm_description   = "Ingest consumer ECS service has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.consumer_service_name
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = { Name = "${var.name_prefix}-consumer-task-count-alarm" }
}

# Ingest queue depth > 10000 — consumer falling behind
resource "aws_cloudwatch_metric_alarm" "ingest_queue_depth" {
  alarm_name          = "${var.name_prefix}-ingest-queue-depth"
  alarm_description   = "Ingest queue depth is high — consumer may be falling behind"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 10000
  treat_missing_data  = "notBreaching"

  dimensions = { QueueName = var.sqs_ingest_queue_name }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = { Name = "${var.name_prefix}-ingest-queue-depth-alarm" }
}

# ── Agent Silence Detection Lambda ────────────────────────────────────────────

data "archive_file" "silence_detector" {
  type        = "zip"
  output_path = "${path.module}/silence_detector.zip"

  source {
    content  = <<-PYTHON
import boto3
import json
import os
from datetime import datetime, timezone, timedelta

CUSTOMERS_TABLE = os.environ['CUSTOMERS_TABLE']
SNS_TOPIC_ARN   = os.environ['SNS_TOPIC_ARN']
SILENCE_MINUTES = int(os.environ.get('SILENCE_MINUTES', '20'))

dynamodb = boto3.resource('dynamodb')
sns      = boto3.client('sns')

def handler(event, context):
    table     = dynamodb.Table(CUSTOMERS_TABLE)
    cutoff    = datetime.now(timezone.utc) - timedelta(minutes=SILENCE_MINUTES)
    response  = table.scan(FilterExpression='SK = :sk', ExpressionAttributeValues={':sk': 'PROFILE'})
    silent    = []

    for customer in response.get('Items', []):
        if customer.get('status') != 'active':
            continue
        last_seen = customer.get('last_agent_seen')
        if not last_seen:
            silent.append(customer['customer_id'])
            continue
        try:
            ts = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            if ts < cutoff:
                silent.append(customer['customer_id'])
        except (ValueError, TypeError):
            silent.append(customer['customer_id'])

    if silent:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'[ALERT] {len(silent)} agent(s) silent > {SILENCE_MINUTES} min',
            Message=json.dumps({'silent_customers': silent, 'checked_at': datetime.now(timezone.utc).isoformat()}),
        )
        # Update agent_status to offline
        for cid in silent:
            try:
                table.update_item(
                    Key={'customer_id': cid, 'SK': 'PROFILE'},
                    UpdateExpression='SET agent_status = :s',
                    ExpressionAttributeValues={':s': 'offline'},
                )
            except Exception:
                pass

    return {'silent_count': len(silent), 'silent_customers': silent}
PYTHON
    filename = "handler.py"
  }
}

resource "aws_iam_role" "silence_detector" {
  name = "${var.name_prefix}-silence-detector"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "silence_detector" {
  name = "silence-detector-policy"
  role = aws_iam_role.silence_detector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:aws:logs:*:*:*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Scan", "dynamodb:UpdateItem"]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [aws_sns_topic.ops_alerts.arn]
      }
    ]
  })
}

resource "aws_lambda_function" "silence_detector" {
  function_name    = "${var.name_prefix}-silence-detector"
  role             = aws_iam_role.silence_detector.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.silence_detector.output_path
  source_code_hash = data.archive_file.silence_detector.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      CUSTOMERS_TABLE = var.dynamodb_customers_table
      SNS_TOPIC_ARN   = aws_sns_topic.ops_alerts.arn
      SILENCE_MINUTES = "20"
    }
  }

  tags = { Name = "${var.name_prefix}-silence-detector" }
}

resource "aws_cloudwatch_event_rule" "silence_detector" {
  name                = "${var.name_prefix}-silence-detector-schedule"
  description         = "Run agent silence detector every 10 minutes"
  schedule_expression = "rate(10 minutes)"
}

resource "aws_cloudwatch_event_target" "silence_detector" {
  rule      = aws_cloudwatch_event_rule.silence_detector.name
  target_id = "silence-detector"
  arn       = aws_lambda_function.silence_detector.arn
}

resource "aws_lambda_permission" "silence_detector" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.silence_detector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.silence_detector.arn
}

# ── CloudWatch Dashboard ──────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.name_prefix

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "SQS Ingest Queue Depth"
          period = 60
          stat   = "Maximum"
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_ingest_queue_name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_dlq_name],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "ECS Running Tasks"
          period = 60
          stat   = "Minimum"
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name],
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", var.consumer_service_name],
          ]
        }
      },
      {
        type = "alarm"
        properties = {
          title  = "Active Alarms"
          alarms = [
            "arn:aws:cloudwatch:${var.aws_region}:*:alarm:${var.name_prefix}-dlq-depth",
            "arn:aws:cloudwatch:${var.aws_region}:*:alarm:${var.name_prefix}-api-task-count",
            "arn:aws:cloudwatch:${var.aws_region}:*:alarm:${var.name_prefix}-consumer-task-count",
          ]
        }
      }
    ]
  })
}

output "ops_alerts_topic_arn" { value = aws_sns_topic.ops_alerts.arn }
