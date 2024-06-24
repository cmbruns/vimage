import subprocess

subprocess.run([*"git update-index -q --refresh".split()])
abb_hash = subprocess.check_output(["git", "describe", "--always", "--dirty", "--broken"], cwd="..")
print(f"vimage_git_hash = {abb_hash.decode().strip()}")
with open("../vmg/git_hash.txt", "w") as fh:
    print(f"vimage_git_hash = {abb_hash.decode().strip()}", file=fh)
