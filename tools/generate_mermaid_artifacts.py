import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp_client import call_tool


SESSION_ID_PATTERN = re.compile(r"SessionID:\s*`([0-9a-fA-F\-]{36})`")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workspace Mermaid report and optionally validate/render with mermaid-cli."
    )
    parser.add_argument("--direction", default="TD", choices=["LR", "TD", "RL", "BT"])
    parser.add_argument("--max-nodes", type=int, default=60)
    parser.add_argument("--mode", default="pipeline", choices=["pipeline", "semantic", "detail"],
                        help="pipeline（預設）：工作流階段觀；semantic：同名合併；detail：1:1 節點")
    parser.add_argument("--snapshot", help="Optional snapshot JSON path instead of live workspace")
    parser.add_argument("--output", help="Output markdown path (used with --save)")
    parser.add_argument("--save", action="store_true", help="Save markdown report to disk")
    parser.add_argument("--validate", action="store_true", help="Validate Mermaid syntax with mmdc")
    parser.add_argument(
        "--render",
        choices=["png", "svg"],
        help="Render Mermaid file to image format with mmdc",
    )
    parser.add_argument("--render-output", help="Explicit render output path")
    parser.add_argument("--mmd-output", help="Explicit .mmd output path")
    return parser.parse_args()


def find_session_id(session_text: str) -> str | None:
    if not isinstance(session_text, str):
        return None
    match = SESSION_ID_PATTERN.search(session_text)
    return match.group(1) if match else None


def require_mmdc() -> str:
    mmdc_path = shutil.which("mmdc")
    if not mmdc_path:
        raise RuntimeError(
            "mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli"
        )
    return mmdc_path


def run_mmdc(input_mmd: Path, output_file: Path) -> None:
    require_mmdc()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["mmdc", "-i", str(input_mmd), "-o", str(output_file), "-b", "transparent"]
    subprocess.run(cmd, check=True)


def resolve_markdown_output(result: dict, requested_output: str | None) -> Path | None:
    saved_to = result.get("savedTo") if isinstance(result, dict) else None
    if isinstance(saved_to, str) and saved_to.strip():
        return Path(saved_to)
    if requested_output:
        return Path(requested_output)
    return None


def write_mermaid_file(mermaid: str, markdown_path: Path | None, override_path: str | None) -> Path:
    if override_path:
        mmd_path = Path(override_path)
    elif markdown_path:
        mmd_path = markdown_path.with_suffix(".mmd")
    else:
        mmd_path = Path("image") / "workspace_logic.mmd"

    mmd_path.parent.mkdir(parents=True, exist_ok=True)
    mmd_path.write_text(mermaid, encoding="utf-8")
    return mmd_path


async def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    args = parse_args()

    tool_args = {
        "direction": args.direction,
        "maxNodes": args.max_nodes,
        "saveToFile": args.save,
        "mode": args.mode,
    }

    if args.output:
        tool_args["outputPath"] = args.output

    if args.snapshot:
        tool_args["snapshotPath"] = args.snapshot
    else:
        sessions_text = await call_tool("list_sessions", {})
        session_id = find_session_id(sessions_text)
        if session_id:
            tool_args["sessionId"] = session_id

    result = await call_tool("generate_workspace_mermaid", tool_args)
    if not isinstance(result, dict):
        print("[ERROR] Unexpected tool response")
        return 1
    if result.get("error"):
        print(f"[ERROR] {result['error']}")
        return 1

    markdown_path = resolve_markdown_output(result, args.output)

    artifact_info = {
        "summary": result.get("summary"),
        "savedTo": str(markdown_path) if markdown_path else None,
        "mmd": None,
        "rendered": None,
        "validated": False,
    }

    if args.validate or args.render:
        mermaid = result.get("mermaid", "")
        if not mermaid:
            print("[ERROR] Mermaid content is empty")
            return 1

        mmd_path = write_mermaid_file(mermaid, markdown_path, args.mmd_output)
        artifact_info["mmd"] = str(mmd_path)

        if args.validate:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_output = Path(tmp_dir) / "validate.png"
                run_mmdc(mmd_path, tmp_output)
            artifact_info["validated"] = True

        if args.render:
            if args.render_output:
                render_path = Path(args.render_output)
            else:
                render_path = mmd_path.with_suffix(f".{args.render}")
            run_mmdc(mmd_path, render_path)
            artifact_info["rendered"] = str(render_path)

    print(json.dumps(artifact_info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
