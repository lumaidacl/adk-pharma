"""Programmatic deployment and lifecycle manager for Vertex AI Agent Engine."""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

from agents.pharma_agent.agent import root_agent

METADATA_PATH: Path = PROJECT_ROOT / "deployment" / "vertex_ai" / "deployment_metadata.json"

DEFAULT_REQUIREMENTS: list[str] = [
    "google-adk>=1.0.0",
    "google-cloud-aiplatform[adk,agent_engines]>=1.93.0",
    "cloudpickle>=3.0.0",
    "python-dotenv>=1.0.1",
]


def get_required_env(var_name: str, placeholder_prefix: str = "your-") -> str:
    """Retrieve and validate a required environment variable."""
    value: str = os.getenv(var_name, "").strip()
    if not value or value.startswith(placeholder_prefix) or value.startswith("gs://your-"):
        raise EnvironmentError(
            f"Missing or placeholder value for '{var_name}'. "
            f"Configure '{var_name}' in your .env file or pass it via CLI/Makefile."
        )
    return value


def normalize_bucket_uri(bucket: str) -> str:
    """Ensure the GCS staging bucket starts with gs://."""
    cleaned: str = bucket.strip()
    return cleaned if cleaned.startswith("gs://") else f"gs://{cleaned}"


def deploy_agent(
    project_id: str,
    location: str,
    staging_bucket: str,
    display_name: str,
) -> None:
    """Package root_agent inside AdkApp and deploy to Vertex AI Agent Engine."""
    normalized_bucket: str = normalize_bucket_uri(staging_bucket)

    print("=" * 80)
    print("Deploying ADK Agent to Vertex AI Agent Engine")
    print(f"  Project        : {project_id}")
    print(f"  Region         : {location}")
    print(f"  Staging Bucket : {normalized_bucket}")
    print(f"  Display Name   : {display_name}")
    print(f"  Agent          : {root_agent.name} ({root_agent.model})")
    print("=" * 80)

    os.chdir(PROJECT_ROOT)

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=normalized_bucket,
    )

    adk_app = agent_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,
    )

    remote_agent = agent_engines.create(
        agent_engine=adk_app,
        requirements=DEFAULT_REQUIREMENTS,
        extra_packages=["./agents"],
        display_name=display_name,
        description=root_agent.description,
    )

    resource_name: str = remote_agent.resource_name
    metadata_payload: dict[str, str] = {
        "resource_name": resource_name,
        "project_id": project_id,
        "location": location,
        "display_name": display_name,
    }
    METADATA_PATH.write_text(
        json.dumps(metadata_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n[SUCCESS] Agent deployed to Vertex AI Agent Engine!")
    print(f"Resource Name : {resource_name}")
    print(f"Metadata File : {METADATA_PATH}")


def list_deployed_agents(project_id: str, location: str) -> None:
    """List existing Vertex AI Agent Engine instances in the target project and region."""
    vertexai.init(project=project_id, location=location)
    instances = list(agent_engines.list())

    if not instances:
        print(f"No Vertex AI Agent Engine instances found in {project_id} ({location}).")
        return

    print(f"Vertex AI Agent Engine instances in {project_id} ({location}):")
    print("-" * 80)
    for engine in instances:
        print(f"Display Name  : {engine.display_name}")
        print(f"Resource Name : {engine.resource_name}")
        print("-" * 80)


def delete_deployed_agent(
    project_id: str,
    location: str,
    resource_name: str | None,
) -> None:
    """Delete a deployed Vertex AI Agent Engine instance by resource name or saved metadata."""
    target_resource: str = (resource_name or "").strip()

    if not target_resource and METADATA_PATH.exists():
        saved_metadata: dict[str, str] = json.loads(
            METADATA_PATH.read_text(encoding="utf-8")
        )
        target_resource = saved_metadata.get("resource_name", "").strip()

    if not target_resource:
        raise ValueError(
            "Provide --resource-name (or AGENT_ENGINE_ID) or ensure "
            f"'{METADATA_PATH.relative_to(PROJECT_ROOT)}' exists from a previous deployment."
        )

    vertexai.init(project=project_id, location=location)
    print(f"Deleting Vertex AI Agent Engine resource: {target_resource} ...")
    agent_engines.delete(resource_name=target_resource, force=True)

    if METADATA_PATH.exists():
        METADATA_PATH.unlink()

    print("[SUCCESS] Agent Engine resource deleted.")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Deploy or manage the Pharma R&D Radar agent on Vertex AI Agent Engine."
    )
    parser.add_argument(
        "--action",
        choices=["deploy", "list", "delete"],
        default="deploy",
        help="Lifecycle operation to execute (default: deploy).",
    )
    parser.add_argument(
        "--resource-name",
        default=os.getenv("AGENT_ENGINE_ID", ""),
        help="Full resource name or ID of the Agent Engine instance (used for delete).",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

    args = build_parser().parse_args()
    project_id: str = get_required_env("GOOGLE_CLOUD_PROJECT")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()

    if args.action == "deploy":
        raw_bucket: str = os.getenv("STAGING_BUCKET", "").strip()
        staging_bucket: str = (
            raw_bucket
            if raw_bucket and raw_bucket != "gs://your-gcp-project-id-adk-staging"
            else f"gs://{project_id}-adk-staging"
        )
        display_name: str = os.getenv(
            "AGENT_ENGINE_DISPLAY_NAME", "Pharma R&D Regulatory Radar"
        ).strip()
        deploy_agent(
            project_id=project_id,
            location=location,
            staging_bucket=staging_bucket,
            display_name=display_name,
        )
    elif args.action == "list":
        list_deployed_agents(project_id=project_id, location=location)
    elif args.action == "delete":
        delete_deployed_agent(
            project_id=project_id,
            location=location,
            resource_name=args.resource_name,
        )


if __name__ == "__main__":
    try:
        main()
    except (EnvironmentError, ValueError) as config_err:
        print(f"[CONFIGURATION ERROR] {config_err}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Operation cancelled by user.", file=sys.stderr)
        sys.exit(130)

