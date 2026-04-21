import re
import subprocess
import time
import sys

SESSION = "codex_capture"
COLS, ROWS = 120, 40


def sh(cmd: str, check=True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


def sh_out(cmd: str) -> str:
    return sh(cmd).stdout


def capture() -> str:
    return sh_out(f"tmux capture-pane -t {SESSION} -p")


# ── CLEAN SESSION ─────────────────────────────────────────────────────────────
sh(f"tmux kill-session -t {SESSION}", check=False)

# ── START CODEX ───────────────────────────────────────────────────────────────
sh(f"tmux new-session -d -s {SESSION} -x {COLS} -y {ROWS} 'codex --no-alt-screen'")

if SESSION not in sh_out("tmux ls || true"):
    sys.exit(1)

# ── WAIT FOR PROMPT ───────────────────────────────────────────────────────────
start = time.time()
while True:
    out = capture()
    if "›" in out:
        break
    if time.time() - start > 20:
        sys.exit(1)
    time.sleep(0.5)

# ── SEND /status ──────────────────────────────────────────────────────────────
sh(f"tmux send-keys -t {SESSION} '/status' Enter")

# ── WAIT FOR STATUS PANEL ─────────────────────────────────────────────────────
start = time.time()
output = ""
retry_sent = False

while True:
    output = capture()

    if "Account:" in output and "Weekly limit:" in output:
        break

    elapsed = time.time() - start

    if elapsed > 5 and not retry_sent:
        sh(f"tmux send-keys -t {SESSION} '/status' Enter")
        retry_sent = True

    if elapsed > 20:
        break

    time.sleep(0.5)

# ── CLEANUP ───────────────────────────────────────────────────────────────────
sh(f"tmux kill-session -t {SESSION}", check=False)

# ── PARSE ─────────────────────────────────────────────────────────────────────
email_match = re.search(r"Account:\s+(\S+@\S+)", output)
quota_match = re.search(r"Weekly limit:\s+(\[.*?\].*?)(?:\s*│|\n)", output)

email = email_match.group(1) if email_match else "N/A"
quota = quota_match.group(1).strip() if quota_match else "N/A"

# ── FINAL OUTPUT ──────────────────────────────────────────────────────────────
print("Email :", email)
print("Quota :", quota)

if email == "N/A" or quota == "N/A":
    sys.exit(2)
