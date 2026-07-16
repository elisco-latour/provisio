"""Increment 23 — proof the core is cloud-agnostic in *mechanism*.

The same primitives (CliTool + ensure + Plan + ExecutionContext) drive AWS and GCP
with no Azure anywhere and no framework changes. Per-CLI specifics (the binary and
its JSON flag) are configured, not assumed — which is the whole point of `CliTool`.
"""
from provisio import CliTool, ExecutionContext, Plan, ensure, step
from provisio.testing import FakeCommandRunner, RecordingReporter


@step("s3-bucket", "Create S3 bucket")
def s3_bucket(ctx: ExecutionContext) -> None:
    aws = ctx.tool("aws")
    ensure(
        ctx,
        describe="s3 bucket 'demo'",
        exists=lambda: aws.exists("s3api", "head-bucket", "--bucket", "demo"),
        create=lambda: aws("s3api", "create-bucket", "--bucket", "demo"),
    )


@step("gcs-bucket", "Create GCS bucket")
def gcs_bucket(ctx: ExecutionContext) -> None:
    gcloud = ctx.tool("gcloud")
    ensure(
        ctx,
        describe="gcs bucket 'demo'",
        exists=lambda: gcloud.exists("storage", "buckets", "describe", "gs://demo"),
        create=lambda: gcloud("storage", "buckets", "create", "gs://demo"),
    )


def test_aws_and_gcp_plan_runs_on_the_same_primitives() -> None:
    fake = FakeCommandRunner()
    fake.stub("aws", "s3api", "head-bucket", returncode=254)  # AWS "not found"
    fake.stub("gcloud", "storage", "buckets", "describe", returncode=1)  # GCP "not found"

    ctx = ExecutionContext(
        reporter=RecordingReporter(),
        tools={
            # Note the different JSON flags per CLI — configured, not assumed.
            "aws": CliTool("aws", fake, json_flags=("--output", "json")),
            "gcloud": CliTool("gcloud", fake, json_flags=("--format=json",)),
        },
    )

    result = Plan([s3_bucket, gcs_bucket]).execute(ctx)

    assert len(result.steps) == 2
    assert fake.issued("aws", "s3api", "create-bucket", "--bucket", "demo")
    assert fake.issued("gcloud", "storage", "buckets", "create", "gs://demo")


def test_json_flags_are_per_cli() -> None:
    fake = FakeCommandRunner().stub("aws", stdout="{}").stub("gcloud", stdout="{}")
    aws = CliTool("aws", fake, json_flags=("--output", "json"))
    gcloud = CliTool("gcloud", fake, json_flags=("--format=json",))
    aws.json("s3api", "list-buckets")
    gcloud.json("storage", "buckets", "list")
    assert fake.calls[0] == ("aws", "s3api", "list-buckets", "--output", "json")
    assert fake.calls[1] == ("gcloud", "storage", "buckets", "list", "--format=json")
