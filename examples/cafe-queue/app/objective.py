"""The only evaluation entry point: forward to the coordinator's counted evaluator."""
import json
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    config = json.loads(Path("config.json").read_text())
    command = config["evaluator_command"] + [str(Path.cwd())]
    raise SystemExit(subprocess.run(command).returncode)
