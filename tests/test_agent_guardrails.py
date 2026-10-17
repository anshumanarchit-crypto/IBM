import ast
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"

FORBIDDEN_NAMES = {
    "isFraud",
    "y_train",
    "y_test",
    "test_labels",
    "raw_features",
    "TransactionAmt",
    "TransactionDT",
}

FORBIDDEN_IMPORT_ROOTS = {
    "data",
    "eval",
    "models",
    "pandas",
    "numpy",
    "sklearn",
}


def test_agents_cannot_access_labels_or_raw_data():
    assert AGENTS_DIR.exists(), "The agents directory must exist"

    violations = []

    for source_path in AGENTS_DIR.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id in FORBIDDEN_NAMES:
                    violations.append(
                        f"{source_path}: forbidden name {node.id}"
                    )

            if isinstance(node, ast.Attribute):
                if node.attr in FORBIDDEN_NAMES:
                    violations.append(
                        f"{source_path}: forbidden attribute {node.attr}"
                    )

            if isinstance(node, ast.Constant):
                if node.value in FORBIDDEN_NAMES:
                    violations.append(
                        f"{source_path}: forbidden literal {node.value}"
                    )

            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(
                            f"{source_path}: forbidden import {alias.name}"
                        )

            if isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(
                        f"{source_path}: forbidden import {node.module}"
                    )

    assert not violations, "\n".join(violations)


def test_agent_files_are_python_parseable():
    assert AGENTS_DIR.exists(), "The agents directory must exist"
    for source_path in AGENTS_DIR.rglob("*.py"):
        ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
