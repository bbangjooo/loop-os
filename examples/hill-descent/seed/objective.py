"""The evaluator: prints one number on the last line. Smaller is better."""

from pathlib import Path

print(Path("value.txt").read_text().strip())
