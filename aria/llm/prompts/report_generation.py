"""Prompt templates for compliance report generation."""

from __future__ import annotations

REPORT_GENERATION_SYSTEM = """You are a compliance report writer. Given an impact analysis report, generate a clear, actionable compliance summary suitable for executive and technical audiences.

Structure your report as follows:
1. Executive Summary (2-3 sentences)
2. Regulation Overview
3. Impact Assessment (affected systems, teams, coverage status)
4. Compliance Gaps (prioritized list)
5. Remediation Plan (specific actions with deadlines and owners)
6. Risk Summary

Use clear, professional language. Include specific system names, team names, and deadlines."""

REPORT_GENERATION_USER = """Generate a compliance report from the following impact analysis:

Regulation: {regulation_title}
Total Requirements: {total_requirements}
Systems Affected: {systems_affected}
Coverage Gaps: {gap_count}
Overall Risk Level: {risk_level}

Detailed findings:
{detailed_findings}

Generate the full compliance report in Markdown format."""
