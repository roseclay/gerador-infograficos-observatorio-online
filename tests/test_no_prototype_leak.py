from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__", "examples", "fixtures", "assets", "config", "output"}
ALLOWED_NAMES = {"dados_info01.csv"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".txt", ".bat", ".csv", ".gitignore"}


def prototype_terms() -> list[str]:
    return [
        "11" + "527",
        "21" + "02",
        "18" + "9",
        "+" + "90 mil",
        "+" + "200",
        "50" + "%",
        "32" + "0",
        "2.200" + "+",
        "Pesqui" + "sadores",
        "Grupos de" + " pesquisa",
    ]


def is_allowed(path: Path) -> bool:
    if path.name in ALLOWED_NAMES:
        return True
    return bool(ALLOWED_PARTS.intersection(path.relative_to(ROOT).parts))


def searchable_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() != ".py":
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    values = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    return "\n".join(values)


def test_prototype_terms_only_remain_in_demo_locations_or_preserved_original():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or is_allowed(path):
            continue
        text = searchable_text(path)
        for term in prototype_terms():
            if term in text:
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
