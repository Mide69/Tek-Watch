"""Notification service — SNS ops alerts, SES customer email, Slack webhooks."""
import asyncio
import json
import logging
from typing import Optional

import boto3
import httpx
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends alert notifications via SNS, SES, and Slack webhooks.

    All boto3 and HTTP calls run in a thread pool executor to avoid blocking
    the asyncio event loop.
    """

    def __init__(self) -> None:
        config = load_config()
        self._sns = boto3.client("sns", region_name=config.aws_region)
        self._ses = boto3.client("ses", region_name=config.aws_region)
        self._ops_topic_arn = config.sns_ops_alerts_topic_arn
        self._ses_from_email = config.ses_from_email
        self._default_slack_webhook = config.slack_webhook_url

    # ── Internal ops alert (SNS) ──────────────────────────────────────────────

    async def send_ops_alert(
        self,
        customer_id: str,
        service: str,
        resource_id: str,
        metric_name: str,
        severity: str,
        current_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        """Publish an alert to the Tek Watch ops SNS topic."""
        if not self._ops_topic_arn:
            logger.debug("SNS ops topic not configured — skipping")
            return

        subject = f"[{severity.upper()}] Tek Watch Alert: {customer_id}"

        if description:
            message = (
                f"Customer: {customer_id}\n"
                f"Service: {service}\n"
                f"Resource: {resource_id}\n"
                f"Type: AI Anomaly\n"
                f"Severity: {severity.upper()}\n\n"
                f"{description}"
            )
        else:
            cv = f"{current_value:.4f}" if current_value is not None else "N/A"
            message = (
                f"Customer: {customer_id}\n"
                f"Service: {service}\n"
                f"Resource: {resource_id}\n"
                f"Metric: {metric_name}\n"
                f"Current Value: {cv}\n"
                f"Threshold: {threshold_value}\n"
                f"Severity: {severity.upper()}"
            )

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._sns.publish(
                    TopicArn=self._ops_topic_arn,
                    Subject=subject[:100],
                    Message=message,
                    MessageAttributes={
                        "severity":    {"DataType": "String", "StringValue": severity},
                        "customer_id": {"DataType": "String", "StringValue": customer_id},
                    },
                ),
            )
            logger.info(
                "Ops alert sent: customer=%s service=%s metric=%s severity=%s",
                customer_id, service, metric_name, severity,
            )
        except ClientError as exc:
            logger.error("SNS publish failed: %s", exc)

    # ── Customer email via SES ────────────────────────────────────────────────

    async def send_customer_email(
        self,
        to_address: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> None:
        """Send an email to a customer via AWS SES."""
        if not self._ses_from_email or not to_address:
            logger.debug("SES not configured or no recipient — skipping email")
            return

        body: dict = {"Text": {"Data": text_body, "Charset": "UTF-8"}}
        if html_body:
            body["Html"] = {"Data": html_body, "Charset": "UTF-8"}

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._ses.send_email(
                    Source=self._ses_from_email,
                    Destination={"ToAddresses": [to_address]},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": body,
                    },
                ),
            )
            logger.info("Email sent to %s: %s", to_address, subject)
        except ClientError as exc:
            logger.error("SES send_email failed: %s", exc)

    async def send_alert_email(
        self,
        to_address: str,
        customer_id: str,
        service: str,
        resource_id: str,
        severity: str,
        metric_name: str,
        current_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        """Send a formatted alert email to a customer."""
        subject = f"[{severity.upper()}] Tek Watch Alert — {service}"
        cv = f"{current_value:.4f}" if current_value is not None else "N/A"

        text_body = (
            f"Tek Watch Alert\n\n"
            f"Severity: {severity.upper()}\n"
            f"Customer: {customer_id}\n"
            f"Service: {service}\n"
            f"Resource: {resource_id}\n"
            f"Metric: {metric_name}\n"
            f"Current Value: {cv}\n"
            f"Threshold: {threshold_value or 'N/A'}\n"
        )
        if description:
            text_body += f"\nDetails:\n{description}\n"
        text_body += "\nView all alerts: https://app.tekwatch.io/alerts\n"

        severity_colors = {
            "critical": "#ef4444",
            "high": "#f97316",
            "warning": "#eab308",
            "info": "#3b82f6",
        }
        color = severity_colors.get(severity, "#6b7280")

        html_body = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
          <div style="background: {color}; padding: 12px 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0; font-size: 16px;">
              [{severity.upper()}] Tek Watch Alert — {service}
            </h2>
          </div>
          <div style="background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td style="padding: 6px 0; color: #6b7280; width: 140px;">Customer</td><td style="padding: 6px 0; font-weight: 600;">{customer_id}</td></tr>
              <tr><td style="padding: 6px 0; color: #6b7280;">Service</td><td style="padding: 6px 0;">{service}</td></tr>
              <tr><td style="padding: 6px 0; color: #6b7280;">Resource</td><td style="padding: 6px 0; font-family: monospace;">{resource_id}</td></tr>
              <tr><td style="padding: 6px 0; color: #6b7280;">Metric</td><td style="padding: 6px 0;">{metric_name}</td></tr>
              <tr><td style="padding: 6px 0; color: #6b7280;">Current Value</td><td style="padding: 6px 0; font-weight: 600; color: {color};">{cv}</td></tr>
              <tr><td style="padding: 6px 0; color: #6b7280;">Threshold</td><td style="padding: 6px 0;">{threshold_value or "N/A"}</td></tr>
            </table>
            {"<p style='margin-top: 16px; color: #374151;'>" + description + "</p>" if description else ""}
            <div style="margin-top: 20px;">
              <a href="https://app.tekwatch.io/alerts" style="background: #4f46e5; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                View Alert Dashboard
              </a>
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #9ca3af;">
              Sent by Tek Watch · Powered by Tek Tribe Ltd
            </p>
          </div>
        </div>
        """

        await self.send_customer_email(to_address, subject, text_body, html_body)

    # ── Slack webhook ─────────────────────────────────────────────────────────

    async def send_slack_alert(
        self,
        customer_id: str,
        service: str,
        resource_id: str,
        metric_name: str,
        severity: str,
        current_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        description: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> None:
        """POST an alert to a Slack incoming webhook."""
        url = webhook_url or self._default_slack_webhook
        if not url:
            logger.debug("No Slack webhook configured — skipping")
            return

        severity_colors = {
            "critical": "#ef4444",
            "high": "#f97316",
            "warning": "#eab308",
            "info": "#3b82f6",
        }
        color = severity_colors.get(severity, "#6b7280")
        cv = f"{current_value:.4f}" if current_value is not None else "N/A"

        fields = [
            {"title": "Customer",  "value": customer_id,           "short": True},
            {"title": "Service",   "value": service,               "short": True},
            {"title": "Resource",  "value": resource_id,           "short": True},
            {"title": "Metric",    "value": metric_name,           "short": True},
            {"title": "Current",   "value": cv,                    "short": True},
            {"title": "Threshold", "value": str(threshold_value or "N/A"), "short": True},
        ]

        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{severity.upper()}] Tek Watch Alert — {service}",
                "title_link": "https://app.tekwatch.io/alerts",
                "text": description or "",
                "fields": fields,
                "footer": "Tek Watch · Tek Tribe Ltd",
                "fallback": f"[{severity.upper()}] {service} alert for {customer_id}: {resource_id}",
            }]
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            logger.info(
                "Slack alert sent: customer=%s service=%s severity=%s",
                customer_id, service, severity,
            )
        except Exception as exc:
            logger.error("Slack webhook failed: %s", exc)
