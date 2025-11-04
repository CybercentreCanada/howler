import json
import re
import shutil
from pathlib import Path

print("Step 1: Copy Files")

ui_path = Path(__file__).parent.parent

dist_path = ui_path / "dist"

if dist_path.exists():
    shutil.rmtree(dist_path)

dist_path.mkdir()

if not (ui_path / "dist" / ".npmrc").exists():
    print("\tCopying .npmrc")
    shutil.copy(ui_path / ".npmrc", ui_path / "dist" / ".npmrc")

if not (ui_path / "dist" / "index.css").exists():
    print("\tCopying index.css")
    shutil.copy(ui_path / "src" / "index.css", ui_path / "dist" / "index.css")

if not (ui_path / "dist" / "package.json").exists():
    print("\tCopying package.json")
    shutil.copy(ui_path / "package.json", ui_path / "dist" / "package.json")

if not (ui_path / "dist" / "README.md").exists():
    print("\tCopying README.md")
    shutil.copy(ui_path.parent / "README.md", ui_path / "dist" / "README.md")
    shutil.copy(ui_path.parent / "README.fr.md", ui_path / "dist" / "README.fr.md")

if not (ui_path / "dist" / "public").exists():
    print("\tRecursively copying public path")
    shutil.copytree(ui_path / "public", ui_path / "dist" / "public")

print("\tCopying source tree")
shutil.copytree(
    ui_path / "src",
    ui_path / "dist",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("test", "tests", "*.test.tsx", "*.test.ts"),
)


print("Step 2: Prepare package.json")

package_json = json.loads((ui_path / "dist" / "package.json").read_text())

if "devDependencies" in package_json:
    print("\tRemoving devDependencies key")
    del package_json["devDependencies"]

if "lint" in package_json:
    print("\tRemoving lint-staged key")
    del package_json["lint-staged"]

if "scripts" in package_json:
    print("\tRemoving scripts key")
    del package_json["scripts"]

if "pnpm" in package_json:
    print("\tRemoving pnpm key")
    del package_json["pnpm"]


package_json["exports"] = dict()
for path in dist_path.rglob("**/*"):
    if path.is_dir():
        continue

    if path.name in [
        "vite-env.d.ts",
        "setupTests.ts",
        "README.md",
        "README.fr.md",
        ".npmrc",
    ]:
        continue

    if "public" in str(path):
        continue

    if path.stem == "index" and path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
        package_json["exports"]["./" + str(path.relative_to(dist_path).parent)] = (
            "./" + str(path.relative_to(dist_path))
        )
    elif path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
        full_path = str(path.relative_to(dist_path))
        package_json["exports"]["./" + re.sub(r"\..+$", "", full_path)] = (
            "./" + full_path
        )
    else:
        package_json["exports"]["./" + str(path.relative_to(dist_path))] = "./" + str(
            path.relative_to(dist_path)
        )

if "." in package_json["exports"]:
    del package_json["exports"]["."]


(dist_path / "package.json").write_text(json.dumps(package_json, indent=2))
root_dirs = [folder for folder in dist_path.glob("*")]


def conditional_import_fix(match: re.Match) -> str:
    import_string: str = match.group(1)
    if import_string.startswith("."):
        return match.group(0)

    if "./" + import_string not in package_json["exports"]:
        return match.group(0)

    print(
        "Rewriting import:",
        import_string,
        f"to @cccsaurora/howler-ui/{import_string}",
    )
    if "from" in match.group(0):
        return f"from '@cccsaurora/howler-ui/{import_string}';"
    else:
        return f"import '@cccsaurora/howler-ui/{import_string}';"


print("Step 3: Fixing imports/exports")
for path in dist_path.rglob("**/*"):
    if path.suffix not in [".ts", ".tsx"]:
        continue

    file_text = path.read_text()
    imports_exports = [
        line
        for line in file_text.splitlines()
        if line.startswith("import") or line.startswith("export")
    ]

    if not imports_exports:
        continue

    path.write_text(
        re.sub(
            r"from '(.+?)';",
            conditional_import_fix,
            re.sub(r"import '(.+?)';", conditional_import_fix, file_text),
        )
    )
