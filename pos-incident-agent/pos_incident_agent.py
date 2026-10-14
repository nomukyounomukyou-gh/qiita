"""Toto Mart POS incident demo agent using OCI Enterprise AI Responses API.

Uses Resource Principal in OCI Hosted Applications and Instance Principal on
the work server. No credentials are stored in this app.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import oci
import requests

from guardrails import evaluate


HERE = Path(__file__).resolve().parent
INSTRUCTIONS = """あなたは架空の小売企業・東都マートの店舗システム障害の初動支援Agentです。
質問で指定されたアラートIDはlookup_alertで照会し、対象システムIDはlookup_systemで台帳を照会してください。
POS障害の優先度と手順はfile_searchでRB-POS-01を検索してから答えてください。
各事実について、アラートID、台帳のシステムID、手順書IDと節番号を根拠として示してください。
監視の観測店舗数を販売停止店舗数と同一視しないでください。
台帳に対象がない場合、類似IDのレコードを流用せず、優先度と担当者を未判定にしてください。
監視レベルcritical/warningを業務優先度P1/P2/P3と混同しないでください。
優先度の理由には、手順書第2章に明記された対象区分・観測店舗数・継続時間だけを使ってください。
手順書にない時間や店舗数の閾値を作らないでください。とくにエスカレーションの時間閾値を推測しないでください。
P1候補なら手順書第3章に従い、一次連絡先とエスカレーション先の両方へ直ちに連絡する下書きにしてください。
P2/P3候補では一次連絡先を示し、影響拡大・長期化時のエスカレーション条件を記してください。
回答は日本語で簡潔な初動対応票にしてください。未確認事項を明示し、復旧操作は提案・実行しないでください。
"""


def load_data(directory: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    raw_alerts = json.loads((directory / "alerts.json").read_text(encoding="utf-8"))
    alerts = {item["alert_id"]: item for item in raw_alerts["alerts"]}
    with (directory / "system_inventory.csv").open(encoding="utf-8-sig", newline="") as fh:
        systems = {item["system_id"]: item for item in csv.DictReader(fh)}
    return alerts, systems


def tools(vector_store_id: str) -> list[dict[str, Any]]:
    return [
        {"type": "file_search", "vector_store_ids": [vector_store_id]},
        {
            "type": "function",
            "name": "lookup_alert",
            "description": "アラートIDを完全一致で検索し、監視記録を返す。対象がなければnot_foundを返す。",
            "parameters": {
                "type": "object",
                "properties": {"alert_id": {"type": "string", "description": "例: ALT-20261008-001"}},
                "required": ["alert_id"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "lookup_system",
            "description": "システムIDを台帳で完全一致検索し、担当部署・連絡先・提供範囲を返す。対象がなければnot_foundを返す。",
            "parameters": {
                "type": "object",
                "properties": {"system_id": {"type": "string", "description": "例: POS-CORE-DB"}},
                "required": ["system_id"],
                "additionalProperties": False,
            },
        },
    ]


def execute_call(name: str, arguments: str, alerts: dict, systems: dict) -> dict[str, Any]:
    try:
        params = json.loads(arguments)
    except json.JSONDecodeError:
        return {"error": "invalid_json_arguments"}
    if name == "lookup_alert":
        key = params.get("alert_id")
        return {"found": key in alerts, "record": alerts.get(key), "source": "alerts.json"}
    if name == "lookup_system":
        key = params.get("system_id")
        return {"found": key in systems, "record": systems.get(key), "source": "system_inventory.csv"}
    return {"error": "unknown_function"}


def extract_text(response: dict[str, Any]) -> str:
    if response.get("output_text"):
        return response["output_text"]
    segments = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    segments.append(part.get("text", ""))
    return "\n".join(segments).strip()


def run_agent(question: str, settings: dict, directory: Path,
              history: list[dict[str, str]] | None = None) -> tuple[str, list[dict[str, Any]]]:
    alerts, systems = load_data(directory)
    base = f"https://inference.generativeai.{settings['region']}.oci.oraclecloud.com/openai/v1"
    session = requests.Session()
    if os.environ.get("OCI_RESOURCE_PRINCIPAL_VERSION"):
        session.auth = oci.auth.signers.get_resource_principals_signer()
    else:
        session.auth = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    session.headers.update({
        "OpenAI-Project": settings["project_id"],
        "opc-compartment-id": settings["compartment_id"],
        "Content-Type": "application/json",
    })
    available_tools = tools(settings["vector_store_id"])
    trace: list[dict[str, Any]] = []
    conversation_input: str | list[dict[str, str]] = question
    if history:
        conversation_input = [
            {"role": item["role"], "content": item["content"]}
            for item in history
        ] + [{"role": "user", "content": question}]
    request_body: dict[str, Any] = {
        "model": settings["model"],
        "instructions": INSTRUCTIONS,
        "input": conversation_input,
        "tools": available_tools,
        "store": True,
    }

    for step in range(6):
        http = session.post(base + "/responses", json=request_body, timeout=180)
        if not http.ok:
            raise RuntimeError(f"Responses API HTTP {http.status_code}: {http.text[:1200]}")
        response = http.json()
        calls = []
        for item in response.get("output", []):
            if item.get("type") == "file_search_call":
                trace.append({"step": step + 1, "tool": "file_search", "status": item.get("status")})
            if item.get("type") == "function_call":
                calls.append(item)
        if not calls:
            answer = extract_text(response)
            if not answer:
                raise RuntimeError("Responses API returned neither function calls nor answer text")
            return answer, trace

        outputs = []
        for call in calls:
            result = execute_call(call.get("name", ""), call.get("arguments", "{}"), alerts, systems)
            trace.append({"step": step + 1, "tool": call.get("name"), "arguments": call.get("arguments"), "found": result.get("found")})
            outputs.append({
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(result, ensure_ascii=False),
            })
        request_body = {
            "model": settings["model"],
            "instructions": INSTRUCTIONS,
            "input": outputs,
            "tools": available_tools,
            "previous_response_id": response["id"],
            "store": True,
        }
    raise RuntimeError("Tool call limit exceeded (6 Responses API rounds)")


def run_guarded_agent(question: str, settings: dict, directory: Path,
                      history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Apply input and output checks around the existing agent workflow."""
    checks = [evaluate(question, settings, "input")]
    if checks[0]["blocked"]:
        return {"answer": "", "trace": [], "checks": checks}
    answer, trace = run_agent(question, settings, directory, history=history)
    checks.append(evaluate(answer, settings, "output"))
    if checks[-1]["blocked"]:
        answer = ""
    return {"answer": answer, "trace": trace, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", help="質問文。省略時は標準入力から読む")
    parser.add_argument("--settings", type=Path, default=HERE / "settings.json")
    parser.add_argument("--data-dir", type=Path, default=HERE)
    parser.add_argument("--show-trace", action="store_true", help="使用したツールを表示")
    args = parser.parse_args()
    question = args.question or sys.stdin.read().strip()
    if not question:
        parser.error("--question or standard input is required")
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    result = run_guarded_agent(question, settings, args.data_dir)
    print(result["answer"] or "Guardrailsが検出したため回答を保留しました。")
    print("\n--- guardrails ---", file=sys.stderr)
    for check in result["checks"]:
        print(json.dumps(check, ensure_ascii=False), file=sys.stderr)
    if args.show_trace:
        print("\n--- tool trace ---", file=sys.stderr)
        for event in result["trace"]:
            print(json.dumps(event, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
