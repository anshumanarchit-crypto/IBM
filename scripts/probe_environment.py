"""Record environment evidence without claiming unsupported capabilities."""

import importlib.metadata
import importlib.util
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "environment.txt"

DISTRIBUTIONS = {
    "pydantic": "pydantic",
    "PyYAML": "yaml",
    "pytest": "pytest",
    "numpy": "numpy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "scipy": "scipy",
    "cryptography": "cryptography",
    "langgraph": "langgraph",
    "llama-cpp-python": "llama_cpp",
    "streamlit": "streamlit",
}


def command_output(command: list[str], timeout: int = 10) -> str:
    """Run a short diagnostic command, reporting failure honestly."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()

        if result.returncode == 0:
            return output or "(command returned no output)"

        return f"(exit code {result.returncode})\nstdout: {output}\nstderr: {error}"

    except FileNotFoundError:
        return "(command not installed)"

    except subprocess.TimeoutExpired:
        return "(diagnostic timed out)"

    except OSError as exc:
        return f"(diagnostic unavailable: {type(exc).__name__})"


def module_status(module_name: str) -> str:
    try:
        return "available" if importlib.util.find_spec(module_name) else "not found"
    except (ImportError, ValueError, ModuleNotFoundError):
        return "not found"


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def read_indicator(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "not available"
    except PermissionError:
        return "permission denied"
    except OSError as exc:
        return f"unavailable ({type(exc).__name__})"


def main() -> None:
    lines = [
        "SIGNALGATE ENVIRONMENT PROBE",
        f"Probe time UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "== Python and operating system ==",
        f"Python version: {sys.version}",
        f"Python executable: {sys.executable}",
        f"Platform: {platform.platform()}",
        f"Architecture: {platform.machine()}",
        f"Operating system: {platform.system()}",
        "",
        "== Command probes ==",
        "uname -m:",
        command_output(["uname", "-m"]),
        "",
        "lscpu:",
        command_output(["lscpu"]),
        "",
        "== Python dependencies ==",
    ]

    for distribution, module_name in DISTRIBUTIONS.items():
        lines.extend(
            [
                f"{distribution}:",
                f"  version: {distribution_version(distribution)}",
                f"  module: {module_status(module_name)}",
            ]
        )

    lines.extend(
        [
            "",
            "== llama.cpp executable probes ==",
        ]
    )

    for executable in ("llama-cli", "llama-server"):
        resolved = shutil.which(executable)
        lines.append(f"{executable}: {resolved or 'not found'}")

        if resolved:
            lines.append(command_output([resolved, "--version"]))

    lines.extend(
        [
            "",
            "== IBM Secure Execution indicators ==",
            ("prot_virt_guest: " + read_indicator(Path("/sys/firmware/uv/prot_virt_guest"))),
            f"/dev/uv exists: {Path('/dev/uv').exists()}",
            "",
            "== Interpretation limits ==",
            "A missing indicator does not prove that all TEE capability is absent.",
            "An indicator value alone is not explicit remote attestation.",
            "This script does not perform or claim hardware attestation.",
            "A detected package or executable does not establish benchmark performance.",
        ]
    )

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Environment report saved to: {OUTPUT}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()