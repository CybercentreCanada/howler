import json
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"

package_json = json.loads((src_path.parent / "dist" / "package.json").read_text())

if "devDependencies" in package_json:
    print("Removing devDependencies key")
    del package_json["devDependencies"]

if "lint" in package_json:
    print("Removing lint-staged key")
    del package_json["lint-staged"]

if "scripts" in package_json:
    print("Removing scripts key")
    del package_json["scripts"]

if "pnpm" in package_json:
    print("Removing pnpm key")
    del package_json["pnpm"]

exports: list[Path] = []
for path in src_path.rglob("**"):
    if path == src_path:
        continue

    exports.append(path.relative_to(src_path))

print(f"Writing {len(exports)} entries to exports")

package_json["exports"] = {f"./{path}/*": f"./{path}/*.js" for path in exports}

(src_path.parent / "dist" / "package.json").write_text(
    json.dumps(package_json, indent=2)
)
