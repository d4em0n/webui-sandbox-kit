"""QA-only OpenAI-compatible endpoint. No real model account or external gateway."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        result = {"object": "list", "data": [{"id": "qa-model", "object": "model", "owned_by": "local-test"}]}
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        message = {"role": "assistant", "content": "The independent sandbox kit model connection works."}
        query = " ".join(str(item.get("content", "")) for item in body.get("messages", []) if item.get("role") == "user")
        if "Kyoto" in query and not any(item.get("role") == "tool" for item in body.get("messages", [])):
            tool = next((tool["function"]["name"] for tool in body.get("tools", [])
                         if "render_frontier_ui" in tool["function"]["name"]), None)
            if tool:
                spec = {"title": "Kyoto QA", "blocks": [{"type": "text", "text": "Independent MCP Apps widget"},
                    {"type": "calculator", "currency": "JPY", "inputs": [{"id": "days", "label": "Days", "value": 2},
                        {"id": "daily", "label": "Daily budget", "value": 7000}],
                     "outputs": [{"label": "Trip total", "expr": "days*daily", "format": "money"}]}]}
                message = {"role": "assistant", "content": None, "tool_calls": [{"id": "qa-call", "type": "function",
                    "function": {"name": tool, "arguments": json.dumps({"spec": spec})}}]}
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            delta = {key: value for key, value in message.items() if key != "role"}
            if delta.get("tool_calls"):
                delta["tool_calls"][0]["index"] = 0
            chunk = {"id": "qa-completion", "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": "qa-model", "choices": [{"index": 0, "delta": delta,
                     "finish_reason": "tool_calls" if "tool_calls" in delta else "stop"}]}
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())
        else:
            data = json.dumps({"id": "qa-completion", "object": "chat.completion", "model": "qa-model", "created": int(time.time()),
                "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
