import os
import subprocess
import json
import urllib.request
import urllib.error
import base64
import os
import subprocess
import json
import urllib.request
import urllib.error
import time

# ================= 配置区域 =================
# 1. 你的 GitHub Token (必须填！否则无法创建 PR;必须有 repo 权限)

# MY_REPO_NAME = "keycloak" 
GITHUB_TOKEN = "your-github-token-here" 

# 2. 你的仓库信息
MY_USERNAME = "your-repo"

# 3. 上游拥有者
UPSTREAM_OWNER = "ai-code-review-evaluation"

# 4. 要处理的仓库列表
#REPO_LIST = ["keycloak", "sentry", "cal.com", "grafana", "discourse"]#Done: cal.com, keycloak, discourse
REPO_LIST = ["keycloak", "sentry",  "grafana", "discourse"] #注意，cal.com需要单独处理，start2,end11

# 5. PR 范围
START_NUM = 1 #cal.com此处需要START_NUM = 2
END_NUM = 10 #cal.com此处需要End_NUM = 11
# ===========================================

def run_cmd(cmd, cwd=None, ignore_error=False, verbose=False):
    """
    执行 Shell 命令
    :param verbose: 如果为 True，则直接将 Git 的输出（包括进度条）打印到屏幕上
    """
    try:
        if verbose:
            # verbose=True 时，不拦截 stdout/stderr，让 Git 直接输出到终端，这样就能看到进度条了
            subprocess.run(cmd, shell=True, cwd=cwd, check=True)
        else:
            # verbose=False 时，静默运行，保持界面整洁
            subprocess.run(
                cmd, 
                shell=True, 
                cwd=cwd, 
                check=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE
            )
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            print(f"   ❌ [Cmd Error] {cmd}")
            # 如果是静默模式报错，把错误日志打印出来方便调试
            if not verbose and e.stderr:
                print(f"   ❌ [Stderr] {e.stderr.decode().strip()}")
        return False
    return True

def github_api_request(url, method="GET", data=None):
    """发送 GitHub API 请求"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "Python-Batch-Script")
    
    if data:
        json_data = json.dumps(data).encode('utf-8')
        req.add_header("Content-Type", "application/json")
        req.data = json_data

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print(f"   ⚠️ [API] PR likely exists or invalid: {e.code}")
        elif e.code == 404:
            print(f"   ⚠️ [API] Resource not found: {url}")
        else:
            print(f"   ❌ [API Error] Code {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"   ❌ [Net Error] {e}")
        return None

def process_single_repo(repo_name):
    """处理单个仓库的所有逻辑"""
    print(f"\n{'='*60}")
    print(f"🚀 Starting Repository: {repo_name}")
    print(f"{'='*60}")

    my_full_repo = f"{MY_USERNAME}/{repo_name}"
    upstream_repo_name = f"{repo_name}-greptile"
    
    root_dir = os.getcwd()
    repo_dir = os.path.join(root_dir, repo_name)

    # --- 1. Clone 或 Update ---
    # 添加 --progress 参数强制显示进度条
    if not os.path.exists(repo_dir):
        print(f"1. Directory not found. Cloning {my_full_repo}...")
        # 注意：这里开启了 verbose=True
        clone_url = f"https://{MY_USERNAME}:{GITHUB_TOKEN}@github.com/{my_full_repo}.git"
        if not run_cmd(f"git clone --progress {clone_url}", verbose=True):
            print("   ❌ Clone failed. Skipping this repo.")
            return
    else:
        print(f"1. Directory exists. Updating origin URL...")
        auth_url = f"https://{MY_USERNAME}:{GITHUB_TOKEN}@github.com/{my_full_repo}.git"
        run_cmd(f"git remote set-url origin {auth_url}", cwd=repo_dir)

    # --- 2. 设置 Upstream ---
    print(f"2. Setting upstream: {UPSTREAM_OWNER}/{upstream_repo_name}")
    upstream_url = f"https://github.com/{UPSTREAM_OWNER}/{upstream_repo_name}.git"
    
    run_cmd("git remote remove upstream_target", cwd=repo_dir, ignore_error=True)
    if not run_cmd(f"git remote add upstream_target {upstream_url}", cwd=repo_dir):
        print("   ❌ Failed to add remote. Skipping this repo.")
        return

    # --- 3. 循环处理 PR ---
    success_count = 0
    for i in range(START_NUM, END_NUM + 1):
        print(f"\n   --- Processing PR #{i} for {repo_name} ---")

        # A. 获取上游 PR 信息
        api_url = f"https://api.github.com/repos/{UPSTREAM_OWNER}/{upstream_repo_name}/pulls/{i}"
        pr_data = github_api_request(api_url)

        if not pr_data:
            print(f"   -> Skipped (Not found or Error).")
            continue

        target_base_branch = pr_data['base']['ref']
        pr_title = pr_data['title']
        pr_body = pr_data['body'] or ""
        local_branch_name = f"mirror-pr-{i}"

        # B. Git Fetch & Push
        print(f"   -> Fetching upstream PR #{i}...")
        # 开启 verbose=True 并添加 --progress
        fetch_cmd = f"git fetch upstream_target pull/{i}/head:{local_branch_name} --progress"
        if not run_cmd(fetch_cmd, cwd=repo_dir, verbose=True):
            print("   -> Fetch failed. Skipping.")
            continue
        
        print("   -> Pushing to origin...")
        # 开启 verbose=True 并添加 --progress
        push_cmd = f"git push origin {local_branch_name}:{local_branch_name} --progress"
        if not run_cmd(push_cmd, cwd=repo_dir, verbose=True):
            print("   -> Push failed. Check Token permissions.")
            continue

        # C. API 创建 PR
        print("   -> Creating PR on your fork...")
        create_pr_url = f"https://api.github.com/repos/{my_full_repo}/pulls"
        payload = {
            "title": f"[Review] {pr_title}",
            "body": f"Mirrored from {UPSTREAM_OWNER}/{upstream_repo_name}#{i}.\n\n{pr_body}",
            "head": local_branch_name,
            "base": target_base_branch
        }

        result = github_api_request(create_pr_url, method="POST", data=payload)
        if result and 'number' in result:
            print(f"   ✅ SUCCESS! Created PR #{result['number']}.")
            success_count += 1
        else:
            print("   -> PR creation finished (Duplicate or Error).")
            
        time.sleep(1)

    print(f"\n🏁 Finished {repo_name}. Created {success_count} new PRs.")

def main():
    print("🔥 Batch Mirror Script Started...")
    for repo in REPO_LIST:
        try:
            process_single_repo(repo)
        except Exception as e:
            print(f"❌ Critical error processing {repo}: {e}")
            continue
    print("\n🎉 All Repositories Processed!")

if __name__ == "__main__":
    main()