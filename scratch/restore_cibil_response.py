import subprocess
import os

def restore():
    print("Running git show to fetch original tracked placeholder...")
    res = subprocess.run(["git", "show", "HEAD:_last_cibil_raw_response.json"], capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 0:
        target_path = os.path.abspath("_last_cibil_raw_response.json")
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(res.stdout)
        print(f"Successfully restored original content to: {target_path}")
    else:
        print("Error fetching content from git HEAD:", res.stderr)

if __name__ == "__main__":
    restore()
