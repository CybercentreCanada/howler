import json
import re
import shutil
from pathlib import Path

print("Step 1: Copy Files")

ui_path = Path(__file__).parent.parent

dist_path = ui_path / "dist"

if not dist_path.exists():
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
shutil.copytree(ui_path / "src", ui_path / "dist", dirs_exist_ok=True)


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
for path in (ui_path / "src").rglob("**/*"):
    if path.is_dir():
        continue

    if path.stem == "index" and path.suffix in [".ts", ".tsx"]:
        package_json["exports"][str(path.relative_to(ui_path / "src").parent)] = (
            "./" + str(path.relative_to(ui_path / "src"))
        )
    elif path.suffix in [".md", ".css"]:
        package_json["exports"][str(path.relative_to(ui_path / "src"))] = "./" + str(
            path.relative_to(ui_path / "src")
        )
    else:
        full_path = str(path.relative_to(ui_path / "src"))
        package_json["exports"][re.sub(r"\..+$", "", full_path)] = "./" + full_path


(ui_path / "dist" / "package.json").write_text(json.dumps(package_json, indent=2))
