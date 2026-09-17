"""Small stdio MCP interface: no general shell or candidate execution tool."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from pathlib import Path

import run as study


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties or {},
        "required": required or [], "additionalProperties": False,
    }}


TEXT = {"type": "string"}
TOOLS = [
    tool("list_files", "List files in this study workspace."),
    tool("read_file", "Read a workspace file. Start with TASK.md, orders.json and baseline.json.",
         {"path": TEXT}, ["path"]),
    tool("write_file", "Write policy.py, a JSON research note, or a backup under scratch/. No execution.",
         {"path": TEXT, "content": TEXT}, ["path", "content"]),
    tool("edit_file", "Replace one exact text occurrence in an editable file. No execution.",
         {"path": TEXT, "old": TEXT, "new": TEXT}, ["path", "old", "new"]),
    tool("syntax_check", "Check policy.py syntax and permitted imports without executing it; no evaluation charge."),
    tool("evaluate", "Execute policy.py on training days. Charges one evaluation including invalid attempts; records source, quality and runtime. The coordinator keeps the best measured valid policy."),
    tool("random_cue", "Draw a reproducible random cue for ideation. Does not execute policy.py.",
         {"pool": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 32},
          "seed": {"type": "integer"}}, ["pool", "seed"]),
]


class WorkspaceTools:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve()

    def path(self, value, *, write=False):
        if not isinstance(value, str) or Path(value).is_absolute():
            raise ValueError("use a relative workspace path")
        path = (self.root / value).resolve()
        relative = path.relative_to(self.root)
        if not relative.parts or ".git" in relative.parts:
            raise ValueError("not a study file")
        if write and not (str(relative) in ("policy.py", "research.json", "exploration.json")
                          or relative.parts[0] == "scratch"):
            raise ValueError("file is protected; write policy.py, research/exploration.json or scratch/")
        return path

    def call(self, name, args):
        if name == "list_files":
            return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")
                          if p.is_file() and ".git" not in p.parts and not p.is_symlink())
        if name == "read_file":
            return self.path(args["path"]).read_text()
        if name in ("write_file", "edit_file"):
            path = self.path(args["path"], write=True)
            if name == "write_file":
                body = args["content"]
            else:
                body = path.read_text()
                if not args["old"] or body.count(args["old"]) != 1:
                    raise ValueError("old text must occur exactly once")
                body = body.replace(args["old"], args["new"], 1)
            if not isinstance(body, str) or len(body) > 150_000:
                raise ValueError("file content must be text of at most 150000 characters")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)
            return {"written": str(path.relative_to(self.root))}
        if name == "syntax_check":
            source = (self.root / "policy.py").read_text()
            compile(source, "policy.py", "exec")
            study.screen_source(source)
            return {"syntax": "PASS", "source_screen": "PASS", "executed": False}
        if name == "evaluate":
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                code = study.evaluate(self.root)
            return {"exit_code": code, "output": capture.getvalue()}
        if name == "random_cue":
            pool, seed = args["pool"], args["seed"]
            if not isinstance(pool, list) or not 1 <= len(pool) <= 32 or not all(isinstance(v, str) for v in pool) or type(seed) is not int:
                raise ValueError("provide 1..32 string cues and an integer seed")
            return {"pool": pool, "seed": seed, "method": "random.Random(seed).choice(pool)",
                    "result": random.Random(seed).choice(pool)}
        raise ValueError("unknown tool")


def serve(workspace):
    workspace_tools = WorkspaceTools(workspace)
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method, params = request["method"], request.get("params", {})
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2024-11-05"),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "cafe-study", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                value = workspace_tools.call(params["name"], params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
            except Exception as error:
                result = {"isError": True, "content": [{"type": "text", "text": str(error)}]}
        elif method in ("resources/list", "prompts/list", "resources/templates/list"):
            result = {{"resources/list": "resources", "prompts/list": "prompts",
                       "resources/templates/list": "resourceTemplates"}[method]: []}
        else:
            result = {}
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    serve(parser.parse_args().workspace)
