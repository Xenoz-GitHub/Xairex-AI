"""Security primitives (offline guardrails, allowlists, path validation).

Phase 1 provides the loopback/cloud-model guardrails used by configuration and
the brain client. Tool permission levels and file/app allowlists arrive in
Phase 4 (see notes/03-TASKS.md).
"""

from xairex.security.policy import is_cloud_model_tag, is_loopback_host, is_loopback_url

__all__ = ["is_cloud_model_tag", "is_loopback_host", "is_loopback_url"]
