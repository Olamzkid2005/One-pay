#!/usr/bin/env python3
"""
CI/CD Deployment Script for KoraPay Integration

This script handles deployment to various environments (staging, production).
It validates configuration, runs tests, deploys, and performs smoke tests.

Usage:
    python scripts/deploy.py --environment=staging
    python scripts/deploy.py --environment=production --dry-run

Requirements: 28.1-28.18
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    environment: str
    app_name: str = "onepay"
    docker_registry: str = "ghcr.io"
    deployment_timeout_seconds: int = 300
    smoke_test_timeout_seconds: int = 60
    rollback_on_failure: bool = True
    run_tests: bool = True


class DeploymentError(Exception):
    """Deployment error."""
    pass


def run_command(cmd: list[str], cwd: str = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def validate_environment(config: DeploymentConfig) -> bool:
    """
    Validate deployment environment.

    Returns:
        True if valid
    """
    print("=" * 60)
    print(f"STEP 1: Validating {config.environment.upper()} Environment")
    print("=" * 60)

    errors = []
    warnings = []

    # Check required environment variables
    required_vars = ["DATABASE_URL"]
    if config.environment == "production":
        required_vars.extend([
            "KORAPAY_SECRET_KEY",
            "KORAPAY_WEBHOOK_SECRET",
        ])

    for var in required_vars:
        if not os.environ.get(var):
            errors.append(f"Required environment variable not set: {var}")

    # Check git status
    returncode, stdout, _ = run_command(["git", "status", "--porcelain"])
    if returncode == 0 and stdout.strip():
        warnings.append("Git working directory is dirty. Commit changes before deploying.")

    # Check git branch
    returncode, stdout, _ = run_command(["git", "branch", "--show-current"])
    if returncode == 0:
        branch = stdout.strip()
        if config.environment == "production" and branch != "main" and branch != "production":
            warnings.append(f"Not on main/production branch (current: {branch})")

    # Print results
    print("\n" + "-" * 40)
    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print("\n❌ Validation FAILED")
        return False

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    print("\n✅ Validation PASSED")
    return True


def run_tests(config: DeploymentConfig) -> bool:
    """
    Run test suite before deployment.

    Returns:
        True if all tests pass
    """
    if not config.run_tests:
        print("\n⚠️  Skipping tests (--no-tests flag)")
        return True

    print("\n" + "=" * 60)
    print("STEP 2: Running Test Suite")
    print("=" * 60)

    # Run unit tests
    print("\nRunning unit tests...")
    returncode, stdout, stderr = run_command(
        ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short", "-q"],
        timeout=120
    )

    if returncode != 0:
        print(f"❌ Unit tests failed:\n{stderr}")
        return False

    print("✅ Unit tests passed")

    # Run integration tests
    print("\nRunning integration tests...")
    returncode, stdout, stderr = run_command(
        ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short", "-q"],
        timeout=180
    )

    if returncode != 0:
        print(f"❌ Integration tests failed:\n{stderr}")
        return False

    print("✅ Integration tests passed")

    # Run property tests
    print("\nRunning property tests...")
    returncode, stdout, stderr = run_command(
        ["python", "-m", "pytest", "tests/property/", "-v", "--tb=short", "-q"],
        timeout=120
    )

    if returncode != 0:
        print(f"❌ Property tests failed:\n{stderr}")
        return False

    print("✅ Property tests passed")

    print("\n✅ All tests passed")
    return True


def build_docker_image(config: DeploymentConfig) -> str:
    """
    Build Docker image for deployment.

    Returns:
        Docker image tag
    """
    print("\n" + "=" * 60)
    print("STEP 3: Building Docker Image")
    print("=" * 60)

    # Get git commit hash
    returncode, stdout, _ = run_command(["git", "rev-parse", "--short", "HEAD"])
    commit_hash = stdout.strip() if returncode == 0 else "unknown"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    image_tag = f"{config.docker_registry}/{config.app_name}:{config.environment}-{timestamp}-{commit_hash}"

    # Build command
    build_cmd = [
        "docker", "build",
        "-t", image_tag,
        "-f", "Dockerfile",
        "."
    ]

    print(f"Building image: {image_tag}")
    returncode, stdout, stderr = run_command(build_cmd, timeout=600)

    if returncode != 0:
        raise DeploymentError(f"Docker build failed:\n{stderr}")

    print(f"✅ Image built: {image_tag}")
    return image_tag


def deploy_to_kubernetes(config: DeploymentConfig, image_tag: str) -> bool:
    """
    Deploy to Kubernetes.

    Returns:
        True if deployment successful
    """
    print("\n" + "=" * 60)
    print("STEP 4: Deploying to Kubernetes")
    print("=" * 60)

    # Update image in deployment
    print(f"Updating Kubernetes deployment with image: {image_tag}")

    # kubectl command would be:
    # kubectl set image deployment/onepay onepay=$image_tag -n $namespace
    # kubectl rollout status deployment/onepay -n $namespace

    namespace = config.environment
    kubectl_cmd = ["kubectl"]

    # Set image
    returncode, stdout, stderr = run_command([
        *kubectl_cmd, "set", "image", f"deployment/{config.app_name}",
        f"{config.app_name}={image_tag}", "-n", namespace
    ])

    if returncode != 0:
        print(f"⚠️  kubectl set image failed: {stderr}")
        print("   (May not be running in Kubernetes environment)")

    # Wait for rollout
    print("Waiting for rollout to complete...")
    returncode, stdout, stderr = run_command([
        *kubectl_cmd, "rollout", "status", f"deployment/{config.app_name}",
        "-n", namespace, "--timeout=300s"
    ], timeout=330)

    if returncode != 0:
        print(f"⚠️  Rollout status failed: {stderr}")
        return False

    print("✅ Deployment successful")
    return True


def run_smoke_tests(config: DeploymentConfig) -> bool:
    """
    Run smoke tests after deployment.

    Returns:
        True if smoke tests pass
    """
    print("\n" + "=" * 60)
    print("STEP 5: Running Smoke Tests")
    print("=" * 60)

    # Determine base URL
    base_urls = {
        "staging": "https://staging-api.onepay.example.com",
        "production": "https://api.onepay.example.com"
    }
    base_url = base_urls.get(config.environment, base_urls["staging"])

    # Test health endpoint
    print(f"Testing health endpoint: {base_url}/health")
    returncode, stdout, stderr = run_command([
        "curl", "-sf", f"{base_url}/health"
    ], timeout=30)

    if returncode != 0:
        print(f"❌ Health check failed")
        return False

    print("✅ Health check passed")

    # Test KoraPay mock mode
    print("Testing KoraPay mock mode...")
    returncode, stdout, stderr = run_command([
        "curl", "-sf", f"{base_url}/api/payments/link",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", '{"amount": 1000, "currency": "NGN"}'
    ], timeout=30)

    if returncode != 0:
        print(f"❌ Mock mode test failed")
        return False

    print("✅ Mock mode test passed")
    print("\n✅ All smoke tests passed")
    return True


def rollback(config: DeploymentConfig) -> bool:
    """
    Rollback to previous version.

    Returns:
        True if rollback successful
    """
    print("\n" + "=" * 60)
    print("ROLLBACK: Reverting to Previous Version")
    print("=" * 60)

    namespace = config.environment
    kubectl_cmd = ["kubectl"]

    # Rollback
    print("Rolling back deployment...")
    returncode, stdout, stderr = run_command([
        *kubectl_cmd, "rollout", "undo", f"deployment/{config.app_name}",
        "-n", namespace
    ])

    if returncode != 0:
        print(f"❌ Rollback failed: {stderr}")
        return False

    print("✅ Rollback successful")
    return True


def deploy(config: DeploymentConfig, dry_run: bool = False) -> bool:
    """
    Execute deployment.

    Returns:
        True if deployment successful
    """
    print("=" * 60)
    print(f"KORAPAY INTEGRATION DEPLOYMENT - {config.environment.upper()}")
    print("=" * 60)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print(f"Dry run: {dry_run}")

    deployment_start = time.time()
    success = False

    try:
        # Step 1: Validate
        if not validate_environment(config):
            return False

        if dry_run:
            print("\n⚠️  DRY RUN - Stopping after validation")
            return True

        # Step 2: Run tests
        if not run_tests(config):
            return False

        # Step 3: Build
        image_tag = build_docker_image(config)

        # Step 4: Deploy
        if not deploy_to_kubernetes(config, image_tag):
            if config.rollback_on_failure:
                rollback(config)
            return False

        # Step 5: Smoke tests
        if not run_smoke_tests(config):
            if config.rollback_on_failure:
                rollback(config)
            return False

        success = True

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        if config.rollback_on_failure:
            rollback(config)
        return False

    finally:
        duration = time.time() - deployment_start
        print("\n" + "=" * 60)
        print("DEPLOYMENT SUMMARY")
        print("=" * 60)
        print(f"Environment: {config.environment}")
        print(f"Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
        print(f"Duration: {duration:.1f}s")
        print(f"Completed at: {datetime.now(timezone.utc).isoformat()}")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="KoraPay Integration Deployment Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/deploy.py --environment=staging
  python scripts/deploy.py --environment=production --dry-run
  python scripts/deploy.py --environment=staging --no-tests

Environment Variables:
  DATABASE_URL        Database connection string
  KORAPAY_SECRET_KEY  KoraPay API secret key (required for production)
  KORAPAY_WEBHOOK_SECRET  KoraPay webhook secret (required for production)
        """
    )

    parser.add_argument(
        "--environment", "-e",
        choices=["staging", "production"],
        default="staging",
        help="Deployment environment (default: staging)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without deploying"
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip running tests"
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Disable automatic rollback on failure"
    )

    args = parser.parse_args()

    config = DeploymentConfig(
        environment=args.environment,
        run_tests=not args.no_tests,
        rollback_on_failure=not args.no_rollback
    )

    success = deploy(config, dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
