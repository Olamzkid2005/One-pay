#!/usr/bin/env python3
"""
Capacity Planning Analysis for KoraPay Integration

This module provides capacity planning calculations and recommendations.

Requirements: 59.21-59.29
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class CapacityMetrics:
    """Capacity metrics for the system."""
    max_concurrent_users_per_instance: int
    max_requests_per_second_per_instance: int
    cpu_usage_per_request_percent: float
    memory_usage_per_request_mb: float
    db_connections_per_instance: int
    scaling_factor_2x: int
    scaling_factor_5x: int
    scaling_factor_10x: int


@dataclass
class ScalingRecommendation:
    """Scaling recommendation."""
    current_instances: int
    recommended_instances_2x: int
    recommended_instances_5x: int
    recommended_instances_10x: int
    notes: list[str]


class CapacityPlanner:
    """Capacity planning calculator."""

    BASE_RESOURCES = {
        "cpu_cores_per_instance": 2,
        "memory_mb_per_instance": 512,
        "max_db_connections_per_instance": 20,
        "max_concurrent_requests_per_instance": 100,
    }

    SCALING_THRESHOLDS = {
        "cpu_scale_up": 70,
        "cpu_scale_down": 30,
        "memory_scale_up": 80,
        "scale_cooldown_minutes": 5,
    }

    def __init__(self):
        self.baseline_metrics = self._calculate_baseline()

    def _calculate_baseline(self) -> dict:
        """Calculate baseline capacity metrics."""
        return {
            "max_concurrent_users": 100,
            "max_requests_per_second": 50,
            "cpu_per_request_percent": 0.5,
            "memory_per_request_mb": 5,
            "db_connections_per_user": 1,
        }

    def calculate_max_concurrent_users(self) -> int:
        """Calculate max concurrent users per instance."""
        cpu_cores = self.BASE_RESOURCES["cpu_cores_per_instance"]
        cpu_per_user = self.baseline_metrics["cpu_per_request_percent"]

        max_users_by_cpu = int((cpu_cores * 100) / cpu_per_user)

        memory_mb = self.BASE_RESOURCES["memory_mb_per_instance"]
        memory_per_user = self.baseline_metrics["memory_per_request_mb"]

        max_users_by_memory = int(memory_mb / memory_per_user)

        return min(max_users_by_cpu, max_users_by_memory)

    def calculate_max_requests_per_second(self) -> int:
        """Calculate max requests per second per instance."""
        concurrent_capacity = self.calculate_max_concurrent_users()

        avg_request_duration_ms = 500
        requests_per_user_per_second = 1000 / avg_request_duration_ms

        return int(concurrent_capacity * requests_per_user_per_second)

    def calculate_scaling_factor(
        self,
        current_users: int,
        target_users: int
    ) -> float:
        """Calculate scaling factor needed."""
        if current_users == 0:
            return 1.0

        return math.ceil(target_users / current_users)

    def calculate_recommended_instances(
        self,
        current_instances: int,
        target_users: int
    ) -> ScalingRecommendation:
        """Calculate recommended instance counts for different scales."""
        max_users_per_instance = self.calculate_max_concurrent_users()

        recommended_2x = math.ceil((current_instances * 2 * max_users_per_instance) / max_users_per_instance)
        recommended_5x = math.ceil((current_instances * 5 * max_users_per_instance) / max_users_per_instance)
        recommended_10x = math.ceil((current_instances * 10 * max_users_per_instance) / max_users_per_instance)

        notes = [
            f"Max concurrent users per instance: {max_users_per_instance}",
            f"Max requests per second per instance: {self.calculate_max_requests_per_second()}",
            f"CPU cores per instance: {self.BASE_RESOURCES['cpu_cores_per_instance']}",
            f"Memory per instance: {self.BASE_RESOURCES['memory_mb_per_instance']}MB",
        ]

        return ScalingRecommendation(
            current_instances=current_instances,
            recommended_instances_2x=max(2, current_instances * 2),
            recommended_instances_5x=max(3, current_instances * 5),
            recommended_instances_10x=max(5, current_instances * 10),
            notes=notes
        )

    def calculate_resource_requirements(
        self,
        requests_per_second: int,
        avg_latency_ms: int
    ) -> dict:
        """Calculate resource requirements for given load."""
        concurrent_requests = int(requests_per_second * avg_latency_ms / 1000)

        cpu_cores_needed = math.ceil(concurrent_requests * self.baseline_metrics["cpu_per_request_percent"] / 100)
        memory_mb_needed = int(concurrent_requests * self.baseline_metrics["memory_per_request_mb"])
        db_connections_needed = min(
            concurrent_requests,
            self.BASE_RESOURCES["max_db_connections_per_instance"]
        )

        instances_needed = max(
            1,
            math.ceil(requests_per_second / self.calculate_max_requests_per_second())
        )

        return {
            "requests_per_second": requests_per_second,
            "concurrent_requests": concurrent_requests,
            "cpu_cores_total": cpu_cores_needed,
            "memory_mb_total": memory_mb_needed,
            "db_connections_total": db_connections_needed,
            "instances_needed": instances_needed,
            "cpu_cores_per_instance": cpu_cores_needed // instances_needed,
            "memory_mb_per_instance": memory_mb_needed // instances_needed,
        }

    def estimate_monthly_cost(
        self,
        instances: int,
        instance_type: str = "medium"
    ) -> dict:
        """Estimate monthly infrastructure cost."""
        costs = {
            "small": {"ec2": 0.05, "rds": 0.02, "cache": 0.01},
            "medium": {"ec2": 0.10, "rds": 0.05, "cache": 0.02},
            "large": {"ec2": 0.20, "rds": 0.10, "cache": 0.04},
        }

        selected = costs.get(instance_type, costs["medium"])

        hours_per_month = 730

        ec2_cost = instances * selected["ec2"] * hours_per_month
        rds_cost = max(1, instances // 2) * selected["rds"] * hours_per_month
        cache_cost = max(1, instances // 4) * selected["cache"] * hours_per_month

        total = ec2_cost + rds_cost + cache_cost

        return {
            "instances": instances,
            "instance_type": instance_type,
            "ec2_monthly": round(ec2_cost, 2),
            "rds_monthly": round(rds_cost, 2),
            "cache_monthly": round(cache_cost, 2),
            "total_monthly": round(total, 2),
            "total_yearly": round(total * 12, 2),
        }


def generate_capacity_report() -> str:
    """Generate a capacity planning report."""
    planner = CapacityPlanner()

    report = []
    report.append("=" * 60)
    report.append("CAPACITY PLANNING REPORT")
    report.append("=" * 60)
    report.append("")

    report.append("BASELINE METRICS:")
    report.append(f"  Max concurrent users per instance: {planner.calculate_max_concurrent_users()}")
    report.append(f"  Max requests per second per instance: {planner.calculate_max_requests_per_second()}")
    report.append("")

    report.append("RESOURCE REQUIREMENTS BY LOAD:")
    for rps in [100, 500, 1000, 5000]:
        resources = planner.calculate_resource_requirements(rps, 500)
        report.append(f"  {rps} RPS: {resources['instances']} instances, "
                     f"{resources['cpu_cores_total']} CPU cores, "
                     f"{resources['memory_mb_total']}MB memory")

    report.append("")
    report.append("SCALING RECOMMENDATIONS (from 2 instances):")
    scaling = planner.calculate_recommended_instances(2, 1000)
    report.append(f"  2x load: {scaling.recommended_instances_2x} instances")
    report.append(f"  5x load: {scaling.recommended_instances_5x} instances")
    report.append(f"  10x load: {scaling.recommended_instances_10x} instances")

    report.append("")
    report.append("COST ESTIMATES:")
    for instances in [2, 4, 10, 20]:
        cost = planner.estimate_monthly_cost(instances, "medium")
        report.append(f"  {instances} instances: ${cost['total_monthly']}/month")

    report.append("")
    report.append("=" * 60)

    return "\n".join(report)


if __name__ == "__main__":
    print(generate_capacity_report())