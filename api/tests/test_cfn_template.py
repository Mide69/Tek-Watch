"""Tests for the CloudFormation template every customer downloads and deploys.

This had no direct test coverage at all before — only _queue_arn, a small
helper, was tested. The template itself is the one artifact in this codebase
that a customer runs unsupervised in their own AWS account; a mistake in it
either fails their deploy outright or, worse, deploys something that looks
successful and silently does the wrong thing (both have happened: a stack
that created a task definition nothing ever ran, and an IAM grant naming a
queue that did not exist).
"""
import yaml
import pytest

from config import APIConfig
from services.cfn_template import generate_agent_template, _queue_arn


def make_config(**overrides) -> APIConfig:
    defaults = dict(
        aws_region="eu-west-2",
        environment="prod",
        log_level="INFO",
        dynamodb_customers_table="tek-watch-prod-customers",
        dynamodb_alerts_table="tek-watch-prod-alerts",
        dynamodb_thresholds_table="tek-watch-prod-thresholds",
        dynamodb_usage_table="tek-watch-prod-usage",
        dynamodb_audit_log_table="tek-watch-prod-audit-log",
        dynamodb_metrics_table="tek-watch-prod-metrics",
        dynamodb_events_table="tek-watch-prod-events",
        cognito_customer_user_pool_id="eu-west-2_abc123",
        cognito_customer_app_client_id="client123",
        cognito_admin_user_pool_id="eu-west-2_admin123",
        cognito_admin_app_client_id="adminclient123",
        anthropic_api_key="sk-ant-test",
        sns_ops_alerts_topic_arn="arn:aws:sns:eu-west-2:834863651414:ops-alerts",
        ses_from_email="noreply@tekwatch.io",
        slack_webhook_url="",
        sqs_ingest_queue_url="https://sqs.eu-west-2.amazonaws.com/834863651414/tek-watch-prod-ingest",
        agent_public_image_uri="public.ecr.aws/s5b4q0k8/tek-watch-agent:latest",
        s3_uploads_bucket="tek-watch-prod-uploads",
        allowed_origins="https://app.tekwatch.io",
    )
    defaults.update(overrides)
    return APIConfig(**defaults)


@pytest.fixture
def template():
    yaml_text = generate_agent_template(
        customer_id="TT-9F4KQ7M2",
        customer_name="Acme Ltd",
        config=make_config(),
    )
    return yaml_text, yaml.safe_load(yaml_text)


class TestQueueArn:
    def test_derives_arn_from_a_real_queue_url(self):
        arn = _queue_arn("https://sqs.eu-west-2.amazonaws.com/834863651414/tek-watch-prod-ingest")
        assert arn == "arn:aws:sqs:eu-west-2:834863651414:tek-watch-prod-ingest"

    def test_falls_back_to_a_wildcard_on_a_malformed_url(self):
        # Better a broad grant than a template that fails to generate at all —
        # the queue's own resource policy still gates cross-account sends.
        assert _queue_arn("not-a-url") == "arn:aws:sqs:*:*:*"

    def test_falls_back_on_an_empty_url(self):
        assert _queue_arn("") == "arn:aws:sqs:*:*:*"


class TestTemplateIsValidYaml:
    def test_generates_parseable_yaml(self, template):
        _, doc = template
        assert doc["AWSTemplateFormatVersion"] == "2010-09-09"

    def test_customer_id_and_name_reach_the_description(self, template):
        _, doc = template
        assert "TT-9F4KQ7M2" in doc["Description"]
        assert "Acme Ltd" in doc["Description"]


class TestApiKeyIsNeverInPlaintext:
    """The API key used to sit in the task definition's Environment array.

    NoEcho on the parameter hides it from `DescribeStacks`, but not from
    `ecs:DescribeTaskDefinition` — a far more commonly granted permission in a
    customer's own account than secretsmanager:GetSecretValue. Anyone with
    read access to ECS could read a customer's agent credential in plaintext.
    """

    def test_api_key_parameter_requires_a_value(self, template):
        _, doc = template
        assert doc["Parameters"]["APIKey"]["MinLength"] == 1

    def test_container_environment_does_not_carry_the_key(self, template):
        _, doc = template
        container = doc["Resources"]["AgentTaskDefinition"]["Properties"]["ContainerDefinitions"][0]
        env_names = {e["Name"] for e in container["Environment"]}
        assert "TEK_WATCH_API_KEY" not in env_names

    def test_container_reads_the_key_from_secrets_manager_instead(self, template):
        _, doc = template
        container = doc["Resources"]["AgentTaskDefinition"]["Properties"]["ContainerDefinitions"][0]
        secrets = {s["Name"]: s["ValueFrom"] for s in container["Secrets"]}
        assert secrets["TEK_WATCH_API_KEY"] == {"Ref": "AgentApiKeySecret"}

    def test_secret_is_seeded_from_the_api_key_parameter(self, template):
        _, doc = template
        secret = doc["Resources"]["AgentApiKeySecret"]
        assert secret["Type"] == "AWS::SecretsManager::Secret"
        assert secret["Properties"]["SecretString"] == {"Ref": "APIKey"}

    def test_only_the_execution_role_can_read_the_secret(self, template):
        _, doc = template
        policies = doc["Resources"]["AgentExecutionRole"]["Properties"]["Policies"]
        stmt = next(
            s
            for p in policies
            for s in p["PolicyDocument"]["Statement"]
            if s["Action"] == "secretsmanager:GetSecretValue"
        )
        assert stmt["Resource"] == {"Ref": "AgentApiKeySecret"}

        # The task role — what the agent's own code runs as — must not also
        # have this grant. Only the execution role resolves container secrets.
        task_role_actions = {
            action
            for p in doc["Resources"]["AgentTaskRole"]["Properties"]["Policies"]
            for s in p["PolicyDocument"]["Statement"]
            for action in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
        }
        assert "secretsmanager:GetSecretValue" not in task_role_actions

    def test_secret_name_is_unique_to_this_stack_not_just_this_customer(self, template):
        """Secrets Manager schedules deletion 30 days out; CloudFormation has
        no property to force it. A fixed name would make "uninstall, then
        reinstall" — a flow this product explicitly offers — fail for a month
        with "already scheduled for deletion". Suffixing the name with the
        stack's own id guarantees a fresh stack never collides with a
        deleted one's secret.
        """
        _, doc = template
        name = doc["Resources"]["AgentApiKeySecret"]["Properties"]["Name"]
        assert isinstance(name, dict) and "Fn::Sub" in name
        template_str, subs = name["Fn::Sub"]
        assert "TT-9F4KQ7M2" in template_str
        assert "StackSuffix" in subs
        assert subs["StackSuffix"] == {
            "Fn::Select": [2, {"Fn::Split": ["/", {"Ref": "AWS::StackId"}]}]
        }


class TestResourceNamesAreNotUnnecessarilySubbed:
    """customer_id is server-generated from a fixed alphabet — never customer
    input — so embedding it in Fn::Sub could never actually be exploited
    today. But Fn::Sub interprets ${...} in whatever string it's given, and
    wrapping a value that needs no CloudFormation substitution in it anyway
    is a landmine for whichever future change reuses this pattern with a
    value that isn't so tightly controlled. A plain string is never
    interpreted for ${} syntax by CloudFormation at all.
    """

    @pytest.mark.parametrize("resource,prop", [
        ("AgentCluster", "ClusterName"),
        ("AgentTaskRole", "RoleName"),
        ("AgentExecutionRole", "RoleName"),
        ("AgentLogGroup", "LogGroupName"),
        ("AgentTaskDefinition", "Family"),
        ("AgentSchedule", "Name"),
    ])
    def test_name_is_a_plain_string(self, template, resource, prop):
        _, doc = template
        value = doc["Resources"][resource]["Properties"][prop]
        assert isinstance(value, str), (
            f"{resource}.{prop} is {value!r}, expected a plain string with no "
            f"Fn::Sub — it carries no CloudFormation variables"
        )
        assert "TT-9F4KQ7M2" in value


class TestSchedulerActuallyRunsTheAgent:
    """The stack used to create a task definition and nothing that ever ran
    it — CREATE_COMPLETE, and no data would ever arrive.
    """

    def test_schedule_rule_targets_the_task_definition(self, template):
        _, doc = template
        rule = doc["Resources"]["AgentSchedule"]
        assert rule["Type"] == "AWS::Events::Rule"
        assert rule["Properties"]["State"] == "ENABLED"
        target = rule["Properties"]["Targets"][0]
        assert target["EcsParameters"]["TaskDefinitionArn"] == {"Ref": "AgentTaskDefinition"}

    def test_scheduler_role_may_only_run_this_stacks_own_cluster(self, template):
        _, doc = template
        policies = doc["Resources"]["AgentSchedulerRole"]["Properties"]["Policies"]
        stmt = next(
            s
            for p in policies
            for s in p["PolicyDocument"]["Statement"]
            if s["Action"] == "ecs:RunTask"
        )
        assert stmt["Condition"]["ArnEquals"]["ecs:cluster"] == {
            "Fn::GetAtt": ["AgentCluster", "Arn"]
        }


class TestSqsGrantMatchesTheRealQueue:
    """The identity policy used to name arn:aws:sqs:*:*:tek-watch-ingest-*,
    which matches nothing the product owns — the queue is
    tek-watch-prod-ingest. The agent collected data and was refused on the
    very last step, with no error until then.
    """

    def test_grant_names_the_exact_queue_from_config(self, template):
        _, doc = template
        policies = doc["Resources"]["AgentTaskRole"]["Properties"]["Policies"]
        stmt = next(
            s
            for p in policies
            for s in p["PolicyDocument"]["Statement"]
            if "sqs:SendMessage" in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
        )
        assert stmt["Resource"] == "arn:aws:sqs:eu-west-2:834863651414:tek-watch-prod-ingest"


class TestSecurityGroupIsOutboundOnly:
    def test_no_ingress_rule_exists(self, template):
        _, doc = template
        sg = doc["Resources"]["AgentSecurityGroup"]["Properties"]
        assert "SecurityGroupIngress" not in sg

    def test_egress_allows_reaching_the_internet(self, template):
        _, doc = template
        egress = doc["Resources"]["AgentSecurityGroup"]["Properties"]["SecurityGroupEgress"][0]
        assert egress["CidrIp"] == "0.0.0.0/0"


class TestTemplateNeverCarriesTheKey:
    """The key used to be embedded as the APIKey Default. NoEcho hides a
    parameter's value from describe-stacks, not a Default in the template body,
    and CloudFormation serves the body to anyone with GetTemplate."""

    def test_generator_cannot_be_given_a_key(self):
        import inspect
        assert "api_key" not in inspect.signature(generate_agent_template).parameters

    def test_key_parameter_has_no_default(self, template):
        _, doc = template
        assert "Default" not in doc["Parameters"]["APIKey"]

    def test_key_parameter_is_noecho(self, template):
        _, doc = template
        assert doc["Parameters"]["APIKey"]["NoEcho"] is True


class TestRunInterval:
    """The schedule and the agent must agree on the interval: the agent uses
    it to decide which runs fetch costs and sweep every region, and when to
    stop. A free-text schedule could not be passed to it."""

    def test_default_is_15_minutes_and_capped_below_the_silence_alarm(self, template):
        _, doc = template
        param = doc["Parameters"]["RunIntervalMinutes"]
        assert param["Default"] == 15
        assert max(param["AllowedValues"]) <= 15
        assert "ScheduleExpression" not in doc["Parameters"]

    def test_schedule_and_agent_read_the_same_parameter(self, template):
        _, doc = template
        rule = doc["Resources"]["AgentSchedule"]["Properties"]
        assert rule["ScheduleExpression"] == {"Fn::Sub": "rate(${RunIntervalMinutes} minutes)"}
        env = doc["Resources"]["AgentTaskDefinition"]["Properties"]["ContainerDefinitions"][0]["Environment"]
        assert {"Name": "TEK_WATCH_RUN_INTERVAL_MINUTES", "Value": {"Ref": "RunIntervalMinutes"}} in env
