#!/usr/bin/env python3
"""
publish.py — 每期生成卡片后的发布入口。

做的事（严格按顺序）：
    1. 把新卡片放进本仓库的 outputs/
    2. 在 movies.json 追加一条元数据
    3. 运行 build_index.py 重建 index.html
    4. git commit + push
    5. **校验远端 commit 与本地一致**
    6. 只有第 5 步通过，才把本地临时卡片移到废纸篓

安全铁律：推送失败 / 校验不过 / 任何异常 —— **绝不动本地卡片**，
并打印明确错误。本地文件是唯一还没进远端的那份，不能先删。

用法（每期生成卡片后调用一次）：
    python3 publish.py \
        --card "/abs/path/outputs/电影推荐-片名.html" \
        --meta '{"n":45,"date":"2026-11-23","title_cn":"片名","title_en":"Original Title","year":1957,"scores":"豆瓣 9.4 · IMDb 9.0","note":"评分口径与奖项备注"}'

meta 字段中 title_cn / title_en / year / scores 若缺失，会尝试从卡片 HTML 兜底解析。
n 与 date 必须显式给出（n 必须等于当前最大期号 + 1）。

演练（在 /tmp 的仓库副本里跑完整本地流程，不推送、不删除、真实仓库零改动）：
    python3 publish.py --card ... --meta ... --dry-run
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent
CARDS = REPO / "outputs"
META_FILE = REPO / "movies.json"
INDEX_SCRIPT = REPO / "build_index.py"


def run(cmd, *, cwd=None, capture=True):
    return subprocess.run(cmd, cwd=cwd or REPO, check=True, text=True,
                          capture_output=capture, encoding="utf-8")


def die(msg):
    print(f"[失败] {msg}", file=sys.stderr)
    print("[安全] 本地卡片未清理；若已清理，可从废纸篓恢复。请检查后重试。", file=sys.stderr)
    sys.exit(1)


def parse_html_fallback(card):
    """从卡片 HTML 兜底解析片名 / 外文名 / 年份 / 评分串。"""
    import html as _html
    s = card.read_text(encoding="utf-8")
    out = {}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    if m:
        out["title_cn"] = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    m = re.search(r'class="en"[^>]*>(.*?)</', s, re.S)
    if m:
        out["title_en"] = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    m = re.search(r"\((\d{4})\)", re.sub(r"<[^>]+>", " ", s.split("<body>", 1)[-1])[:400])
    if m:
        out["year"] = int(m.group(1))
    body = re.sub(r"<[^>]+>", " ", s.split("<body>", 1)[-1])
    body = re.sub(r"\s+", " ", body)
    found = []
    for label, pat in [("豆瓣", r"豆瓣\s*([\d.]+)"), ("IMDb", r"IMDb\s*([\d.]+)"),
                       ("RT", r"RT(?:专业)?\s*(\d+)%?"), ("MC", r"MC\s*(\d+)")]:
        mm = re.search(pat, body)
        if mm:
            found.append(f"{label} {mm.group(1)}")
    if found:
        out["scores"] = " · ".join(found)
    return out


def repo_slug():
    """由 origin 解析 owner/repo。"""
    url = run(["git", "remote", "get-url", "origin"]).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def pages_base():
    owner, repo = repo_slug()
    return f"https://{owner}.github.io/{repo}/" if owner else None


def local_pipeline(work_repo, card, meta, card_src):
    """在 work_repo 里完成『复制 → 元数据 → 重建索引 → 提交』，不推送。"""
    outputs = work_repo / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    dst = outputs / card.name
    if card_src.resolve() != dst.resolve():
        shutil.copy2(card_src, dst)

    movies = json.loads((work_repo / "movies.json").read_text(encoding="utf-8"))
    if any(d["n"] == meta["n"] for d in movies):
        die(f"第 {meta['n']} 期已存在于 movies.json（防止重复推送）")
    movies.append({**meta, "file": card.name})
    movies.sort(key=lambda d: d["n"])
    (work_repo / "movies.json").write_text(
        json.dumps(movies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    r = subprocess.run([sys.executable, str(work_repo / "build_index.py")],
                       cwd=work_repo, text=True, capture_output=True, encoding="utf-8")
    if r.returncode != 0:
        die(f"build_index.py 失败：{r.stderr.strip() or r.stdout.strip()}")
    print("  " + r.stdout.strip())

    run(["git", "add", "-A"], cwd=work_repo)
    run(["git", "commit", "-m", f"add: 第 {meta['n']} 期 {meta['title_cn']}"], cwd=work_repo)
    return movies


def verify_index(work_repo, expected):
    """校验生成的索引页数据条数与链接。"""
    s = (work_repo / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const MOVIES = (\[.*?\]);\n", s, re.S)
    if not m:
        die("index.html 里找不到内嵌数据")
    data = json.loads(m.group(1))
    if len(data) != expected:
        die(f"index.html 数据条数 {len(data)}，应为 {expected}")
    bad = [d["link"] for d in data if not (work_repo / d["link"]).is_file()]
    if bad:
        die(f"索引存在失效链接：{bad}")
    print(f"  索引校验通过：{len(data)} 条 / 0 失效链接")


def main():
    ap = argparse.ArgumentParser(description="生成后推送到仓库并清理本地卡片")
    ap.add_argument("--card", required=True, help="新生成卡片的绝对路径")
    ap.add_argument("--meta", required=True, help="单行 JSON 元数据")
    ap.add_argument("--dry-run", action="store_true", help="在临时副本演练，不推送不删除")
    args = ap.parse_args()

    card = Path(args.card).expanduser().resolve()
    if not card.is_file() or card.suffix.lower() != ".html":
        die(f"卡片文件不存在或不是 HTML：{card}")
    try:
        meta = json.loads(args.meta)
    except json.JSONDecodeError as e:
        die(f"--meta 不是合法 JSON：{e}")

    if "n" not in meta or "date" not in meta:
        die("--meta 必须包含 n（期号）和 date（YYYY-MM-DD）")
    for k in ("title_cn", "title_en", "year", "scores", "note"):
        meta.setdefault(k, "")
    fallback = parse_html_fallback(card)
    for k, v in fallback.items():
        if not meta.get(k):
            meta[k] = v
    if not meta.get("title_cn"):
        die("无法确定片名（title_cn），请在 --meta 中显式给出")
    meta["year"] = int(meta["year"]) if meta["year"] else 0

    movies = json.loads(META_FILE.read_text(encoding="utf-8"))
    expect_n = max(d["n"] for d in movies) + 1
    if meta["n"] != expect_n:
        die(f"期号应为 {expect_n}，收到 {meta['n']}（防止跳号或重复）")

    print(f"[发布] 第 {meta['n']} 期《{meta['title_cn']}》→ {card.name}")

    # ---- 演练模式：在 /tmp 副本里跑完整本地流程，真实仓库零改动 ----
    if args.dry_run:
        print("[演练] 在临时副本中执行，不推送、不删除本地卡片")
        tmp = Path(tempfile.mkdtemp(prefix="movie-publish-dryrun-"))
        try:
            copy = tmp / "repo"
            shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns("__pycache__"))
            got = local_pipeline(copy, card, meta, card)
            verify_index(copy, len(got))
            print(f"[演练通过] 本地流程无误；真实仓库未改动，卡片仍在：{card}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return

    # ---- 正常模式 ----
    status = run(["git", "status", "--porcelain"]).stdout.strip()
    if status:
        die(f"仓库有未提交改动，请先处理再发布：\n{status}")

    local_pipeline(REPO, card, meta, card)
    verify_index(REPO, len(movies) + 1)

    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    print("[推送] git push origin main …")
    try:
        run(["git", "push", "origin", "main"], capture=False)
    except subprocess.CalledProcessError as e:
        die(f"git push 失败：{e}")

    # 关键校验：远端 HEAD 必须与本地一致
    try:
        remote = run(["git", "ls-remote", "origin", "refs/heads/main"]).stdout.strip().split()[0]
    except Exception as e:
        die(f"无法读取远端 HEAD：{e}")
    if remote != head:
        die(f"远端 HEAD({remote[:8]}) 与本地({head[:8]}) 不一致，推送可能未生效")

    # 附加校验：远端 tree 里确实有新卡片（gh 不可用时仅提示，不阻断）
    try:
        owner, repo = repo_slug()
        r = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/git/trees/main?recursive=1",
             "--jq", ".tree[].path"],
            cwd=REPO, text=True, capture_output=True, encoding="utf-8", timeout=30)
        if r.returncode == 0:
            target = f"outputs/{card.name}"
            if target not in r.stdout.splitlines():
                die(f"远端 tree 中未找到 {target}")
            print(f"[远端校验] commit {head[:8]} 已同步，{target} 存在 ✓")
        else:
            print("[提示] gh 远端 tree 校验跳过（commit 一致性校验已通过）", file=sys.stderr)
    except (OSError, subprocess.SubprocessError):
        print("[提示] gh 不可用，跳过 tree 校验（commit 一致性校验已通过）", file=sys.stderr)

    # ---- 只有全部通过，才清理本地卡片 ----
    trash = shutil.which("trash")
    if not trash:
        die("系统无 trash 命令，为安全起见不删除本地卡片（可手动清理）")
    r = subprocess.run([trash, str(card)], text=True, capture_output=True, encoding="utf-8")
    if r.returncode != 0:
        die(f"移到废纸篓失败：{r.stderr.strip()}（本地卡片仍在）")
    if card.exists():
        die("trash 返回成功但卡片仍在原位置，清理未生效（本地卡片仍在）")

    base = pages_base()
    online = (base + "outputs/" + urllib.parse.quote(card.name)) if base else None
    print(f"[完成] 本地卡片已移入废纸篓（可恢复）：{card}")
    if online:
        print(f"[在线] {online}")
        print(f"[索引] {base}")
    print("[提示] present_files 请交付上面的在线 URL，不要再交付本地路径。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # 任何未预期异常都不允许静默删掉本地文件
        die(f"未预期异常：{type(exc).__name__}: {exc}")
