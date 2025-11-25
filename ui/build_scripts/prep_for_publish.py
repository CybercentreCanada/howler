import json
import os
import shutil
from pathlib import Path

print("Step 1: Copy Files")

ui_path = (Path(__file__).parent.parent).resolve()
src_path = (ui_path / "src").resolve()
dist_path = (ui_path / "dist").resolve()

if not (dist_path / ".npmrc").exists():
    print("\tCopying .npmrc")
    shutil.copy(ui_path / ".npmrc", dist_path / ".npmrc")

if not (dist_path / "README.md").exists():
    print("\tCopying .README.md")
    shutil.copy(ui_path.parent / "README.md", dist_path / "README.md")
    shutil.copy(ui_path.parent / "README.fr.md", dist_path / "README.fr.md")

if not (dist_path / "index.css").exists():
    print("\tCopying index.css")
    shutil.copy(src_path / "index.css", dist_path / "index.css")

if not (dist_path / "package.json").exists():
    print("\tCopying package.json")
    shutil.copy(ui_path / "package.json", dist_path / "package.json")

if not (dist_path / "public").exists():
    print("\tRecursively copying public path")
    shutil.copytree(ui_path / "public", dist_path / "public")

print("\tCopying Markdown")
for markdown in src_path.rglob("**/*.md"):
    if not (dist_path / markdown.relative_to(src_path).parent).exists():
        os.makedirs(dist_path / markdown.relative_to(src_path).parent)

    write_file = Path(
        os.path.splitext(dist_path / markdown.relative_to(src_path))[0] + ".md.js"
    )

    write_file.write_text(f"export default {json.dumps(markdown.read_text())}")

print("Step 2: Prepare package.json")

package_json = json.loads((dist_path / "package.json").read_text())

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
for path in src_path.rglob("**"):
    if path == src_path:
        continue

    exports.append(path.relative_to(src_path))

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


print(f"\tWriting {len(exports)} entries to exports")

package_json["exports"] = {"./i18n": "./i18n.js", "./index.css": "./index.css"}
for path in exports:
    if "." in path.name:
        package_json["exports"][f"./{path.parent.relative_to(src_path)}"] = (
            f"./{path.parent.relative_to(src_path)}/index.js"
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

(dist_path / "package.json").write_text(json.dumps(package_json, indent=2))

print("Step 3: Rewiring imports")
for js_file in (dist_path).rglob("**/*.js"):
    current_content = js_file.read_text()

    if "'i18n'" in current_content:
        current_content = current_content.replace(
            "'i18n'", "'@cccsaurora/howler-ui/i18n'"
        )

    for path in exports:
        if f"'{path}" not in current_content:
            continue

        current_content = current_content.replace(
            f"from '{path}", f"from '@cccsaurora/howler-ui/{path}"
        )

    js_file.write_text(current_content)

for js_file in (dist_path).rglob("**/*.ts"):
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


print("Step 4: Copy type declaration files")
for dts in src_path.rglob("**/*.d.ts"):
    if dts.name in ["vite-env.d.ts", "globals.d.ts"]:
        continue

    dest = dist_path / dts.relative_to(src_path)

    if not dest.parent.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(dts, dist_path / dts.relative_to(src_path))

print("-" * 80)
