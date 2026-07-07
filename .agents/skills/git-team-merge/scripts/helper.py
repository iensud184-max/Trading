#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import sys
import json
import re
import os
from datetime import datetime

def run_cmd(args, check=True, text=True):
    try:
        res = subprocess.run(args, capture_output=True, text=text, check=check)
        return res.stdout.strip(), res.stderr.strip(), res.returncode
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error executing command {' '.join(args)}: {e.stderr}", file=sys.stderr)
            sys.exit(1)
        return e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else "", e.returncode

def list_prs():
    stdout, stderr, code = run_cmd(["gh", "pr", "list", "--state", "open", "--json", "number,title,author,headRefName,headRepositoryOwner"], check=False)
    if code != 0:
        print(f"GitHub CLI pr list failed: {stderr}", file=sys.stderr)
        sys.exit(1)
    
    try:
        prs = json.loads(stdout)
        print(json.dumps(prs, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Failed to parse PR JSON output: {e}", file=sys.stderr)
        sys.exit(1)

def get_pr_info(pr_num):
    stdout, stderr, code = run_cmd(["gh", "pr", "view", str(pr_num), "--json", "number,title,headRefName,headRepositoryOwner,headRepository"], check=False)
    if code != 0:
        print(f"GitHub CLI pr view failed: {stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(stdout)

def test_merge(pr_num, base):
    pr_info = get_pr_info(pr_num)
    head_owner = pr_info["headRepositoryOwner"]["login"]
    head_branch = pr_info["headRefName"]
    
    head_repo_name = pr_info["headRepository"]["name"]
    repo_url = f"https://github.com/{head_owner}/{head_repo_name}.git"

    print(f"Simulating merge of PR #{pr_num} ({head_owner}:{head_branch}) into base {base}...")

    orig_branch, _, _ = run_cmd(["git", "branch", "--show-current"])
    stash_created = False
    
    status_out, _, _ = run_cmd(["git", "status", "--porcelain"])
    if status_out.strip():
        print("Saving current unstaged changes via git stash...")
        run_cmd(["git", "stash"])
        stash_created = True

    temp_branch = f"test-merge-PR-{pr_num}"
    
    run_cmd(["git", "checkout", base], check=False)
    run_cmd(["git", "branch", "-D", temp_branch], check=False)
    
    print(f"Creating temporary branch {temp_branch} from {base}...")
    run_cmd(["git", "checkout", "-b", temp_branch, f"origin/{base}"])

    print(f"Pulling remote changes from {repo_url} branch {head_branch}...")
    pull_stdout, pull_stderr, pull_code = run_cmd(["git", "pull", "--no-rebase", repo_url, head_branch], check=False)

    conflicts = []
    if pull_code != 0:
        conflict_files_out, _, _ = run_cmd(["git", "diff", "--name-only", "--diff-filter=U"], check=False)
        conflicts = [f.strip() for f in conflict_files_out.strip().split("\n") if f.strip()]
        print(f"CONFLICTS DETECTED in: {conflicts}")
        
        report_path = "conflict_report.md"
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(f"# Conflict Analysis Report for PR #{pr_num}\n\n")
            rf.write(f"* **Source PR**: #{pr_num} ({head_owner}:{head_branch})\n")
            rf.write(f"* **Target Base**: {base}\n")
            rf.write(f"* **Date**: {datetime.now().isoformat()}\n\n")
            rf.write("## Conflict Details\n\n")
            
            for cf in conflicts:
                rf.write(f"### File: [{cf}](file://{os.path.abspath(cf)})\n\n")
                rf.write("```diff\n")
                try:
                    with open(cf, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    in_conflict = False
                    conflict_block = []
                    for idx, line in enumerate(lines, start=1):
                        if line.startswith("<<<<<<<"):
                            in_conflict = True
                        if in_conflict:
                            conflict_block.append(f"{idx}: {line}")
                        if line.startswith(">>>>>>>"):
                            in_conflict = False
                            rf.write("".join(conflict_block) + "\n")
                            conflict_block = []
                except Exception as file_err:
                    rf.write(f"Failed to read file conflict markers: {file_err}\n")
                rf.write("```\n\n")
        print(f"Conflict report written to: {report_path}")
    else:
        print("Auto-merge successful! No conflicts found.")

    print(f"Cleaning up temp branch and returning to {orig_branch}...")
    run_cmd(["git", "merge", "--abort"], check=False)
    run_cmd(["git", "checkout", orig_branch])
    run_cmd(["git", "branch", "-D", temp_branch], check=False)
    
    if stash_created:
        print("Restoring unstaged changes via git stash pop...")
        run_cmd(["git", "stash", "pop"], check=False)

    result = {
        "pr": pr_num,
        "base": base,
        "mergeable": len(conflicts) == 0,
        "conflicts": conflicts
    }
    print(json.dumps(result, indent=2))

def verify_build():
    print("Verifying build integrity...")
    py_files = ["backend/routes/trade.py", "backend/routes/home.py", "backend/routes/keys.py", "backend/services/binance_client.py"]
    for pf in py_files:
        if os.path.exists(pf):
            _, stderr, code = run_cmd(["python3", "-m", "py_compile", pf], check=False)
            if code != 0:
                print(f"BUILD VERIFICATION FAILED: Compile error in {pf}\nError: {stderr}", file=sys.stderr)
                sys.exit(1)
            print(f"  Compile OK: {pf}")

    if os.path.exists("package.json"):
        print("Running frontend npm build check...")
        _, build_err, build_code = run_cmd(["npm", "run", "build"], check=False)
        if build_code != 0:
            print(f"BUILD VERIFICATION FAILED: npm run build failed\nError: {build_err}", file=sys.stderr)
            sys.exit(1)
        print("  Frontend build OK.")
    
    print("SUCCESS: Build verification passed.")

def merge_pr(pr_num, base):
    print(f"Triggering merge for PR #{pr_num} into {base} on GitHub...")
    _, stderr, code = run_cmd(["gh", "pr", "merge", str(pr_num), "--merge"], check=False)
    if code != 0:
        print(f"GitHub CLI pr merge failed: {stderr}", file=sys.stderr)
        sys.exit(1)
    
    print("Synchronizing local git branch...")
    run_cmd(["git", "checkout", base])
    run_cmd(["git", "pull", "origin", base])
    print(f"PR #{pr_num} merged and synchronized locally on branch {base}.")

def release_main(base, main_branch):
    print(f"Creating release PR from {base} to {main_branch}...")
    title = f"chore: {base} 브랜치를 {main_branch} 브랜치로 통합"
    body = "이모지 없이 작성된 통합 릴리즈 자동 생성 PR입니다."
    
    stdout, stderr, code = run_cmd(["gh", "pr", "create", "--base", main_branch, "--head", base, "--title", title, "--body", body], check=False)
    if code != 0:
        print(f"Failed to create release PR: {stderr}", file=sys.stderr)
        sys.exit(1)
    
    pr_url = stdout.strip()
    print(f"Release PR created: {pr_url}")
    
    match = re.search(r"/pull/(\d+)", pr_url)
    if not match:
        print("Could not extract PR number from URL.")
        sys.exit(0)
        
    pr_num = match.group(1)
    print(f"Merging Release PR #{pr_num}...")
    run_cmd(["gh", "pr", "merge", pr_num, "--merge"])
    print(f"Integration release to {main_branch} finished successfully.")

def main():
    parser = argparse.ArgumentParser(description="Git Team Merge Helper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-prs", help="List all open pull requests")

    test_parser = subparsers.add_parser("test-merge", help="Simulate a PR merge and find conflicts")
    test_parser.add_argument("--pr", type=int, required=True, help="PR number")
    test_parser.add_argument("--base", type=str, default="develop", help="Target base branch (default: develop)")

    subparsers.add_parser("verify-build", help="Run project compilation and build verification")

    merge_parser = subparsers.add_parser("merge-pr", help="Merge a PR on GitHub and pull base locally")
    merge_parser.add_argument("--pr", type=int, required=True, help="PR number")
    merge_parser.add_argument("--base", type=str, default="develop", help="Base branch name")

    release_parser = subparsers.add_parser("release-main", help="Create and merge PR from develop to main")
    release_parser.add_argument("--base", type=str, default="develop", help="Head branch (develop)")
    release_parser.add_argument("--main", type=str, default="main", help="Base branch (main)")

    args = parser.parse_args()

    if args.command == "list-prs":
        list_prs()
    elif args.command == "test-merge":
        test_merge(args.pr, args.base)
    elif args.command == "verify-build":
        verify_build()
    elif args.command == "merge-pr":
        merge_pr(args.pr, args.base)
    elif args.command == "release-main":
        release_main(args.base, args.main)

if __name__ == "__main__":
    main()
