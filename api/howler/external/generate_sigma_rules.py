import shlex
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp


def main():
    """Run the script to generate sigma rule lookups"""
    print("Generating sigma yaml")

    git_dir = Path(mkdtemp())
    subprocess.call(shlex.split((f"git clone git@github.com:SigmaHQ/sigma.git {git_dir} --depth 1")))

    output_dir = Path(__file__).parent.parent / "odm" / "sigma"
    if not output_dir.exists():
        output_dir.mkdir()

    print("Copying files")
    for network_yaml in (git_dir / "rules" / "network").glob("**/*.yml"):
        print(f"  {network_yaml.relative_to(((git_dir / 'rules' / 'network')))}")
        new_file = output_dir / network_yaml.name
        shutil.copyfile(network_yaml, new_file)

    shutil.rmtree(git_dir)

    print("Done!")


if __name__ == "__main__":
    main()
