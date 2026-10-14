"""Session chat UI for the Toto Mart incident-response agent."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pos_incident_agent import HERE, run_guarded_agent


SESSION_ID = re.compile(r"^[a-f0-9-]{36}$")
SAMPLE_HEADING = re.compile(r"^## 質問(\d+)：(.+)$")
SESSION_TTL_SECONDS = 12 * 60 * 60


def load_samples(path: Path) -> list[dict[str, str]]:
    """Read the demo questions so the UI follows demo_questions.md."""
    samples: list[dict[str, str]] = []
    candidate = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = SAMPLE_HEADING.match(line)
        if match:
            candidate = {"number": match.group(1), "title": match.group(2)}
        elif candidate and line.startswith("> "):
            candidate["question"] = re.sub(r"`([^`]+)`", r"\1", line[2:].strip())
            samples.append(candidate)
            candidate = None
    return samples


def page(samples: list[dict[str, str]]) -> bytes:
    embedded = json.dumps(samples, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return (HERE / "chat.html").read_text(encoding="utf-8").replace("__SAMPLES_JSON__", embedded).encode("utf-8")


class SessionStore:
    """Ephemeral conversation context; the browser keeps the visible transcript."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._lock = threading.Lock()

    def _prune(self) -> None:
        cutoff = time.time() - SESSION_TTL_SECONDS
        self._items = {key: value for key, value in self._items.items() if value[0] >= cutoff}
        if len(self._items) > 200:
            oldest = sorted(self._items, key=lambda key: self._items[key][0])[:len(self._items) - 200]
            for key in oldest:
                del self._items[key]

    def history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._prune()
            item = self._items.get(session_id)
            return [part.copy() for part in item[1]] if item else []

    def add_turn(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            self._prune()
            previous = self._items.get(session_id, (0, []))[1]
            history = previous + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
            self._items[session_id] = (time.time(), history[-12:])


def handler_factory(settings: dict, data_dir: Path):
    samples = load_samples(data_dir / "demo_questions.md")
    html_page = page(samples)
    sessions = SessionStore()

    class Handler(BaseHTTPRequestHandler):
        def send_payload(self, content: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, value: dict, status: int = 200) -> None:
            self.send_payload(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def do_GET(self) -> None:
            if self.path in ("/health", "/ready"):
                self.send_json({"status": "ok"})
            elif self.path == "/":
                self.send_payload(html_page, "text/html; charset=utf-8")
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/":
                self.send_error(404)
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self.send_json({"error": "JSON形式で送信してください。"}, 415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_json({"error": "リクエストを読み取れませんでした。"}, 400)
                return
            if length < 1 or length > 30000:
                self.send_json({"error": "質問が長すぎます。"}, 413)
                return
            try:
                request = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                self.send_json({"error": "リクエストを読み取れませんでした。"}, 400)
                return
            if not isinstance(request, dict):
                self.send_json({"error": "リクエストを読み取れませんでした。"}, 400)
                return
            question = request.get("question", "")
            session_id = request.get("sessionId", "")
            if not isinstance(question, str) or not question.strip() or len(question) > 4000:
                self.send_json({"error": "質問を4000文字以内で入力してください。"}, 400)
                return
            if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
                self.send_json({"error": "セッションを開始し直してください。"}, 400)
                return
            question = question.strip()
            try:
                result = run_guarded_agent(question, settings, data_dir, history=sessions.history(session_id))
                if result["answer"]:
                    sessions.add_turn(session_id, question, result["answer"])
                result["trace"] = [
                    {"tool": item.get("tool"), "found": item.get("found")}
                    for item in result["trace"]
                ]
                self.send_json(result)
            except Exception:
                logging.exception("Agent request failed")
                self.send_json({"error": "GuardrailsまたはAgentの処理に失敗しました。接続設定と権限を確認してください。"}, 502)

        def log_message(self, format: str, *args) -> None:
            # Questions and answers are intentionally omitted from access logs.
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--settings", type=Path, default=HERE / "settings.json")
    parser.add_argument("--data-dir", type=Path, default=HERE)
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(settings, args.data_dir))
    print(f"POS incident demo: http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
