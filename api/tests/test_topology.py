"""The dependency graph, and the honesty rules that keep it usable.

The plan claimed TekWatch "traces an event through the customer's specific AWS
service dependency topology". It did not: it named the resource that changed
and stopped. These tests pin what the graph may and may not say.
"""
import pytest

from services import correlation, topology


def res(service, resource_id, dims=None, name=None, region="eu-west-2"):
    return {
        "resource_id": resource_id,
        "resource_name": name or resource_id,
        "region": region,
        "metrics": {},
        "dimensions": dims or {},
    }


def bucket(name):
    return res("s3", name, {"public_access_blocked": "False"})


def distribution(dist_id, origins, name="cdn.example.com"):
    return res("cloudfront", dist_id, {"domain": f"{dist_id}.cloudfront.net", "origins": origins}, name=name)


class TestOriginParsing:
    @pytest.mark.parametrize("origin,expected", [
        ("assets.s3.eu-west-2.amazonaws.com", "assets"),
        ("assets.s3.amazonaws.com", "assets"),
        ("assets.s3-website-eu-west-2.amazonaws.com", "assets"),
        ("my.dotted.bucket.s3.eu-west-2.amazonaws.com", "my.dotted.bucket"),
    ])
    def test_bucket_names_are_read_out_of_origin_domains(self, origin, expected):
        assert topology.bucket_from_origin(origin) == expected

    @pytest.mark.parametrize("origin", [
        "alb-123.eu-west-2.elb.amazonaws.com",
        "origin.example.com",
        "",
    ])
    def test_origins_that_are_not_buckets_return_nothing(self, origin):
        assert topology.bucket_from_origin(origin) is None


class TestGraph:
    def test_a_distribution_is_joined_to_the_bucket_it_serves(self):
        inv = {
            "s3": [bucket("acme-assets")],
            "cloudfront": [distribution("E1", "acme-assets.s3.eu-west-2.amazonaws.com")],
        }
        graph = topology.build(inv)
        [edge] = [e for e in graph.edges if e.relationship == topology.SERVES]
        assert edge.source == "cloudfront:E1"
        assert edge.target == "s3:acme-assets"
        # AWS states this relationship, so it is not hedged.
        assert edge.confidence == topology.DIRECT

    def test_an_origin_we_do_not_hold_a_bucket_for_creates_no_edge(self):
        inv = {
            "s3": [bucket("acme-assets")],
            "cloudfront": [distribution("E1", "someone-elses.s3.eu-west-2.amazonaws.com")],
        }
        assert [e for e in topology.build(inv).edges if e.relationship == topology.SERVES] == []

    def test_resources_sharing_a_security_group_are_joined_but_marked_inferred(self):
        inv = {
            "ec2": [res("ec2", "i-1", {"security_groups": "sg-app", "vpc_id": "vpc-1"})],
            "rds": [res("rds", "prod-db", {"engine": "postgres", "security_groups": "sg-app,sg-db",
                                           "vpc_id": "vpc-1"})],
        }
        graph = topology.build(inv)
        [edge] = [e for e in graph.edges if e.relationship == topology.SHARES_SECURITY_GROUP]
        assert {edge.source, edge.target} == {"ec2:i-1", "rds:prod-db"}
        # Shared membership does not establish connectivity.
        assert edge.confidence == topology.INFERRED
        assert edge.as_dict()["why"] == "Both share security group sg-app; connectivity not verified."

    def test_a_security_group_with_one_member_joins_nothing(self):
        inv = {"ec2": [res("ec2", "i-1", {"security_groups": "sg-lonely"})]}
        assert [e for e in topology.build(inv).edges if e.relationship == topology.SHARES_SECURITY_GROUP] == []

    def test_resources_are_joined_to_the_network_they_run_in(self):
        inv = {"rds": [res("rds", "prod-db", {"engine": "postgres", "vpc_id": "vpc-1"})]}
        graph = topology.build(inv)
        assert "vpc:vpc-1" in graph.nodes
        [edge] = [e for e in graph.edges if e.relationship == topology.RUNS_IN]
        assert (edge.source, edge.target) == ("rds:prod-db", "vpc:vpc-1")

    def test_resources_that_report_no_relationships_produce_no_edges(self):
        inv = {"ec2": [res("ec2", "i-1")], "s3": [bucket("lonely")]}
        graph = topology.build(inv)
        assert len(graph.nodes) == 2
        assert graph.edges == []

    def test_an_empty_account_is_an_empty_graph(self):
        graph = topology.build({})
        assert graph.as_dict() == {"nodes": [], "edges": []}


class TestImpact:
    def test_a_public_bucket_reports_the_distribution_publishing_it(self):
        inv = {
            "s3": [bucket("acme-assets")],
            "cloudfront": [distribution("E1", "acme-assets.s3.eu-west-2.amazonaws.com", name="cdn.acme.co.uk")],
        }
        result = topology.impact(topology.build(inv), "s3:acme-assets")
        assert result["total"] == 1
        assert result["serves"][0]["name"] == "cdn.acme.co.uk"
        assert "published to the internet" in topology.summarise(result)

    @pytest.mark.parametrize("count", [1, 2])
    def test_a_database_reports_shared_group_associations(self, count):
        inv = {
            "ec2": [res("ec2", "i-1", {"security_groups": "sg-app"}, name="web-1"),
                    res("ec2", "i-2", {"security_groups": "sg-app"}, name="web-2")][:count],
            "rds": [res("rds", "prod-db", {"engine": "postgres", "security_groups": "sg-app"})],
        }
        result = topology.impact(topology.build(inv), "rds:prod-db")
        names = [f"web-{i}" for i in range(1, count + 1)]
        assert {e["name"] for e in result["reachable_from"]} == set(names)
        assert result["total"] == count
        noun = "resource shares" if count == 1 else "resources share"
        assert topology.summarise(result) == (
            f"Related resources: {count} other {noun} a security group with it "
            f"({', '.join(names)}); connectivity not verified."
        )

    def test_a_resource_we_have_never_seen_returns_nothing_rather_than_failing(self):
        result = topology.impact(topology.build({}), "s3:ghost")
        assert result["resource"] is None and result["total"] == 0

    def test_a_resource_with_no_neighbours_says_nothing(self):
        result = topology.impact(topology.build({"s3": [bucket("lonely")]}), "s3:lonely")
        assert topology.summarise(result) == ""

    def test_impact_stops_at_one_hop(self):
        # Two hops through a shared VPC reaches the whole account and tells the
        # reader nothing useful.
        inv = {
            "ec2": [res("ec2", "i-1", {"security_groups": "sg-a", "vpc_id": "vpc-1"}),
                    res("ec2", "i-2", {"security_groups": "sg-b", "vpc_id": "vpc-1"})],
            "rds": [res("rds", "db", {"engine": "postgres", "security_groups": "sg-a", "vpc_id": "vpc-1"})],
        }
        result = topology.impact(topology.build(inv), "rds:db")
        assert {e["resource_id"] for e in result["reachable_from"]} == {"i-1"}


class TestIncidentsCarryTheImpact:
    def test_an_exposed_bucket_incident_names_the_distribution_serving_it(self):
        inv = {
            "s3": [bucket("acme-assets")],
            "cloudfront": [distribution("E1", "acme-assets.s3.eu-west-2.amazonaws.com", name="cdn.acme.co.uk")],
            "cloudtrail": [],
        }
        [incident] = [i for i in correlation.correlate(inv) if i["type"] == "s3_public_exposure"]
        impact = incident["service_impact"]
        assert impact["total"] == 1
        assert impact["serves"][0]["name"] == "cdn.acme.co.uk"
        assert "cdn.acme.co.uk" in impact["summary"]

    def test_a_database_incident_names_shared_group_associations(self):
        inv = {
            "rds": [res("rds", "prod-db", {"engine": "postgres", "publicly_accessible": "True",
                                           "security_groups": "sg-app"})],
            "ec2": [res("ec2", "i-1", {"security_groups": "sg-app"}, name="web-1")],
            "cloudtrail": [],
        }
        [incident] = [i for i in correlation.correlate(inv) if i["type"] == "database_publicly_reachable"]
        impact = incident["service_impact"]
        assert impact["reachable_from"][0]["name"] == "web-1"
        assert impact["reachable_from"][0]["why"] == (
            "Both share security group sg-app; connectivity not verified."
        )
        assert impact["summary"] == (
            "Related resources: 1 other resource shares a security group with it "
            "(web-1); connectivity not verified."
        )

    def test_every_incident_carries_the_field_even_when_nothing_is_joined(self):
        inv = {"s3": [bucket("lonely")], "cloudtrail": []}
        for incident in correlation.correlate(inv):
            assert incident["service_impact"]["total"] == 0
            assert incident["service_impact"]["summary"] == ""

    def test_an_account_wide_incident_has_no_resource_to_trace(self):
        # "Logging was switched off" is not about one resource, so there is
        # nothing to trace and the field stays empty rather than inventing one.
        inv = {
            "cloudtrail": [
                {"resource_id": "trails", "resource_name": "trails",
                 "metrics": {"trails_logging_count": 0}, "dimensions": {}},
                {"resource_id": "evt-1", "resource_name": "StopLogging", "region": "eu-west-2",
                 "metrics": {"high_risk_event": "StopLogging"},
                 "dimensions": {"event_name": "StopLogging", "username": "deploy-bot",
                                "source_ip": "203.0.113.9", "resource_name": "org-trail",
                                "event_time": "2026-09-18T09:00:00+00:00"}},
            ],
        }
        [incident] = [i for i in correlation.correlate(inv) if i["type"] == "audit_logging_disabled"]
        assert incident["service_impact"]["total"] == 0
