#!/usr/bin/env python3
"""
自动更新 + Git 提交推送包装脚本
直接运行，无需人工审批
"""

import os, sys, subprocess, datetime

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r"C:\Users\14506\.workbuddy\binaries\python\versions\3.13.12\python.exe"
SCRIPT = os.path.join(PROJECT, "scripts", "auto_update.py")

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def main():
    log("=" * 55)
    log("  Auto Runner 开始")
    log("=" * 55)

    # Step 1: 运行自动更新脚本
    log("Step 1: 运行 auto_update.py...")
    result = subprocess.run(
        [PYTHON, SCRIPT],
        cwd=PROJECT,
        capture_output=True, text=True, timeout=120
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        log(f"❌ auto_update.py 失败 (code={result.returncode})")
        return False

    # Step 2: Git 提交
    log("Step 2: Git commit...")
    today = datetime.date.today().isoformat()
    r = subprocess.run(
        ["git", "add", "index_modified.html", "index.html", "data/"],
        cwd=PROJECT, capture_output=True, text=True
    )
    if r.returncode != 0:
        log(f"⚠️ git add 失败: {r.stderr.strip()}")
        # 可能没有变更

    r = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=PROJECT, capture_output=True, text=True
    )
    if r.returncode == 0:
        log("⏭️  没有新的变更，跳过 commit")
    else:
        r = subprocess.run(
            ["git", "commit", "-m", f"data: auto-update {today}"],
            cwd=PROJECT, capture_output=True, text=True
        )
        if r.returncode == 0:
            log(f"✅ Commit 成功: {r.stdout.strip()[:100]}")
        else:
            log(f"⚠️  git commit 结果: {r.stderr.strip()[:200]}")

    # Step 3: Git 推送
    log("Step 3: Git push...")
    r = subprocess.run(
        ["git", "push", "origin", "master"],
        cwd=PROJECT, capture_output=True, text=True, timeout=30
    )
    if r.returncode == 0:
        log(f"✅ Push 成功: {r.stdout.strip()[:100]}")
    else:
        log(f"⚠️  Push 失败 (网络不可达?): {r.stderr.strip()[:200]}")

    log("=" * 55)
    log("✅ Auto Runner 完成")
    log("=" * 55)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
