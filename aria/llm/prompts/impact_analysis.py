"""Prompt templates for regulatory impact analysis."""

from __future__ import annotations

IMPACT_ANALYSIS_SYSTEM = """You are a compliance impact analyst. Given information about a regulation's requirements, affected internal systems, and existing policy coverage, you must:

1. Assess the coverage status of each requirement against each affected system
2. Identify gaps where no policy document addresses a requirement
3. Assign risk levels based on obligation type and coverage gaps
4. Recommend remediation actions with priorities

Coverage status definitions:
- covered: An existing policy fully addresses the requirement for this system
- partial: An existing policy partially addresses the requirement but has gaps
- gap: No existing policy addresses this requirement for this system

Risk level definitions:
- low: Informational requirements with existing coverage
- medium: Requirements with partial coverage or non-critical gaps
- high: Critical requirements with no coverage affecting important systems
- critical: High-risk requirements (prohibitions, mandatory assessments) with no coverage"""


IMPACT_ANALYSIS_USER = """Analyze the regulatory impact based on the following data:

Regulation: {regulation_title} (ID: {regulation_id})

Requirements and affected systems:
{impact_data}

Existing policy documents:
{policy_data}

Generate a structured impact report with coverage assessments and remediation tasks."""
