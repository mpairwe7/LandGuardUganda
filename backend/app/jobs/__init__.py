"""Periodic governance jobs (escalation, parity audit) + their scheduler.

Canonical implementations live here so they are importable both by the CLI
wrappers in ``backend/scripts/`` (manual / cron invocation) and by the
in-process scheduler (``app.jobs.scheduler``) started in the API lifespan.
"""
