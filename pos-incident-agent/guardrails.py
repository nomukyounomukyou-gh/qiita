"""OCI Generative AI Guardrails checks for the incident-response agent."""

from __future__ import annotations

from typing import Any

import oci
import requests


def _signer():
    if __import__("os").environ.get("OCI_RESOURCE_PRINCIPAL_VERSION"):
        return oci.auth.signers.get_resource_principals_signer()
    return oci.auth.signers.InstancePrincipalsSecurityTokenSigner()


def evaluate(text: str, settings: dict[str, Any], stage: str) -> dict[str, Any]:
    """Evaluate text and make the demo's policy decision. Fail closed on errors."""
    if stage not in ("input", "output"):
        raise ValueError("stage must be input or output")
    region = settings["region"]
    url = f"https://inference.generativeai.{region}.oci.oraclecloud.com/20231130/actions/applyGuardrails"
    configs: dict[str, Any] = {
        "contentModerationConfig": {"categories": ["OVERALL"]},
        "personallyIdentifiableInformationConfig": {},
    }
    if stage == "input":
        configs["promptInjectionConfig"] = {}
    payload = {
        "compartmentId": settings["compartment_id"],
        "guardrailConfigs": configs,
        "guardrailVersionConfig": {"guardrailVersion": settings["guardrail_version"]},
        "input": {"type": "TEXT", "content": text},
    }
    with requests.Session() as session:
        session.auth = _signer()
        response = session.post(url, json=payload, timeout=60)
        if not response.ok:
            raise RuntimeError(f"ApplyGuardrails HTTP {response.status_code}: {response.text[:400]}")
        data = response.json()

    results = data.get("results", {})
    moderation = results.get("contentModeration") or {}
    categories = moderation.get("categories") or []
    overall = next((entry.get("score") for entry in categories if entry.get("name") == "OVERALL"), None)
    injection = (results.get("promptInjection") or {}).get("score") if stage == "input" else None
    pii = results.get("personallyIdentifiableInformation") or []
    if overall is None or (stage == "input" and injection is None):
        raise RuntimeError("ApplyGuardrails returned incomplete evaluation results")
    blocked = overall >= 1 or (injection is not None and injection >= 1)
    return {
        "stage": stage,
        "blocked": blocked,
        "moderation": overall,
        "injection": injection,
        "pii": [item.get("label", "UNKNOWN") for item in pii],
        "version": (data.get("guardrailVersion") or {}).get("version", settings["guardrail_version"]),
        "action": "保留" if blocked else ("通知して続行" if pii else "通過"),
    }
