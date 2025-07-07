import json
import os
import shutil
from pathlib import Path

print("Step 1: Copy Files")

ui_path = Path(__file__).parent.parent

if not (ui_path / "dist" / ".npmrc").exists():
    print("\tCopying .npmrc")
    shutil.copy(ui_path / ".npmrc", ui_path / "dist" / ".npmrc")

if not (ui_path / "dist" / "index.css").exists():
    print("\tCopying index.css")
    shutil.copy(ui_path / "src" / "index.css", ui_path / "dist" / "index.css")

if not (ui_path / "dist" / "package.json").exists():
    print("\tCopying package.json")
    shutil.copy(ui_path / "package.json", ui_path / "dist" / "package.json")

if not (ui_path / "dist" / "public").exists():
    print("\tRecursively copying public path")
    shutil.copytree(ui_path / "public", ui_path / "dist" / "public")

print("\tCopying Markdown")
for markdown in (ui_path / "src").rglob("**/*.md"):
    if not (ui_path / "dist" / markdown.relative_to(ui_path / "src").parent).exists():
        os.makedirs(ui_path / "dist" / markdown.relative_to(ui_path / "src").parent)

    write_file = Path(
        os.path.splitext(ui_path / "dist" / markdown.relative_to(ui_path / "src"))[0]
        + ".md.js"
    )

    write_file.write_text(f"export default {json.dumps(markdown.read_text())}")

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

exports: list[Path] = []
for path in (ui_path / "src").rglob("**"):
    if path == (ui_path / "src"):
        continue

    exports.append(path.relative_to(ui_path / "src"))

    if (
        index := next(
            (
                path / _index
                for _index in ["index.ts", "index.tsx"]
                if (path / _index).exists()
            ),
            None,
        )
    ) is not None:
        exports.append(index)


print(f"\t Writing {len(exports)} entries to exports")

package_json["exports"] = {"./i18n": "./i18n.js", "./index.css": "./index.css"}
for path in exports:
    if "." in path.name:
        package_json["exports"][f"./{path.parent.relative_to(ui_path / "src")}"] = (
            f"./{path.parent.relative_to(ui_path / "src")}/index.js"
        )
    elif str(path).startswith("locales"):
        package_json["exports"][f"./{path}/*.json"] = f"./{path}/*.json"
    elif "markdown" in str(path):
        package_json["exports"][f"./{path}/*.md"] = f"./{path}/*.md.js"
    elif str(path).startswith("utils"):
        package_json["exports"][f"./{path}/*"] = f"./{path}/*.js"
        package_json["exports"][f"./{path}/*.json"] = f"./{path}/*.json"
    else:
        package_json["exports"][f"./{path}/*"] = f"./{path}/*.js"

(ui_path / "dist" / "package.json").write_text(json.dumps(package_json, indent=2))

print("Step 3: Rewiring imports")
for js_file in (ui_path / "dist").rglob("**/*.js"):
    current_content = js_file.read_text()

    if "'i18n'" in current_content:
        current_content = current_content.replace(
            "'i18n'", "'@cccsaurora/howler-ui/i18n'"
        )

    for path in exports:
        if f"'{path}" not in current_content:
            continue

        current_content = current_content.replace(
            f"'{path}", f"'@cccsaurora/howler-ui/{path}"
        )

    js_file.write_text(current_content)

for js_file in (ui_path / "dist").rglob("**/*.ts"):
    current_content = js_file.read_text()

    if "'i18n'" in current_content:
        current_content = current_content.replace(
            "'i18n'", "'@cccsaurora/howler-ui/i18n'"
        )

    for path in exports:
        if f"'{path}" not in current_content:
            continue

        print("\tFixing import", path)

        current_content = current_content.replace(
            f"'{path}", f"'@cccsaurora/howler-ui/{path}"
        )

    js_file.write_text(current_content)

print("-" * 80)
