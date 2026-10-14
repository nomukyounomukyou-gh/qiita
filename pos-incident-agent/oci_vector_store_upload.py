"""Register the fictional demo documents in your own OCI vector store.

Run on OCI Compute using Instance Principal, or in a Resource Principal runtime.
Only the three explicit knowledge files are uploaded. Credentials are not read
from local configuration directories and no connection results are saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import oci
import requests

HERE = Path(__file__).resolve().parent
DOCUMENTS = ("pos_incident_runbook.md", "system_inventory_for_rag.md", "alerts_for_rag.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "list", "search"))
    parser.add_argument("--settings", type=Path, default=HERE / "settings.json")
    parser.add_argument("--region")
    parser.add_argument("--project-id")
    parser.add_argument("--compartment-id")
    parser.add_argument("--store-id")
    parser.add_argument("--directory", type=Path, default=HERE)
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    region = args.region or settings["region"]
    project = args.project_id or settings["project_id"]
    compartment = args.compartment_id or settings["compartment_id"]
    store = args.store_id or settings["vector_store_id"]
    if any(not value or "<" in value for value in (region, project, compartment, store)):
        parser.error("Replace placeholders in settings.json with your own resource values")
    base = f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"
    with requests.Session() as session:
        session.auth = (oci.auth.signers.get_resource_principals_signer()
                        if os.environ.get("OCI_RESOURCE_PRINCIPAL_VERSION")
                        else oci.auth.signers.InstancePrincipalsSecurityTokenSigner())
        session.headers.update({"OpenAI-Project": project, "opc-compartment-id": compartment})

        def call(method: str, path: str, **kwargs):
            result = session.request(method, base + path, timeout=60, **kwargs)
            result.raise_for_status()
            return result.json()

        def listing(path: str) -> list[dict]:
            items = []
            params = {"limit": 100}
            while True:
                page = call("GET", path, params=params)
                entries = page.get("data", [])
                items.extend(entries)
                if not page.get("has_more") or not entries:
                    return items
                params["after"] = entries[-1]["id"]

        store_path = f"/vector_stores/{store}/files"
        if args.action == "list":
            print(json.dumps(listing(store_path), ensure_ascii=False, indent=2))
            return
        if args.action == "search":
            result = call("POST", f"/vector_stores/{store}/search", json={
                "query": "POS-CORE-DB 32店舗 18分 P1候補 判定条件", "max_num_results": 3})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        attached = {item["id"] for item in listing(store_path)}
        existing = {item["filename"]: item["id"] for item in listing("/files")}
        target_ids = []
        for name in DOCUMENTS:
            path = args.directory / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            upload_name = f"{path.stem}-{digest}{path.suffix}"
            file_id = existing.get(upload_name)
            if not file_id:
                with path.open("rb") as source:
                    uploaded = call("POST", "/files", files={
                        "file": (upload_name, source, "text/markdown")}, data={"purpose": "assistants"})
                file_id = uploaded["id"]
            if file_id not in attached:
                call("POST", store_path, json={"file_id": file_id})
            target_ids.append(file_id)
            print(f"Registered: {name}", flush=True)

        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            states = [call("GET", f"{store_path}/{file_id}").get("status") for file_id in target_ids]
            if all(state == "completed" for state in states):
                print("All three documents indexed: completed")
                return
            if any(state in ("failed", "cancelled") for state in states):
                raise RuntimeError(f"Indexing failed: {states}")
            time.sleep(5)
        raise TimeoutError("Indexing did not complete in 300 seconds; use the list action to check status")


if __name__ == "__main__":
    main()
