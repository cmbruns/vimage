import subprocess

subprocess.run([*"git update-index -q --refresh".split()])
abb_hash = subprocess.check_output(["git", "describe", "--always", "--dirty", "--broken"], cwd="..")
line = f"vimage_git_hash = {abb_hash.decode().strip()}"
# Print to output
print(line)
# Write to file where the app can access it
with open("../vmg/git_hash.txt", "w") as fh:
    print(line, file=fh)
