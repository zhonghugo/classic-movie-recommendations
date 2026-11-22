#!/usr/bin/env python3
"""
重建索引页 index.html。

数据源：同目录下的 movies.json（44 条元数据）。
卡片文件：同目录下的 outputs/ 目录。

用法：
    python3 build_index.py

新增一期时：
    1. 把新卡片放进 outputs/
    2. 在 movies.json 末尾加一条（n / date / title_cn / title_en / year /
       scores / note / file，字段含义见 README）
    3. 运行本脚本，提交生成的 index.html

只依赖 Python 标准库，数据内嵌进生成的 HTML，因此 index.html 单独用
浏览器打开（file://）也能正常搜索和跳转，不依赖任何服务器或 CDN。
"""
import json
import pathlib
import html

ROOT = pathlib.Path(__file__).resolve().parent
movies = json.loads((ROOT / "movies.json").read_text(encoding="utf-8"))
movies.sort(key=lambda d: d["n"])

# 校验：期号连续、引用的文件真实存在
nums = [d["n"] for d in movies]
assert nums == list(range(1, len(movies) + 1)), f"期号不连续: {nums}"
missing = [d["file"] for d in movies if not (ROOT / "outputs" / d["file"]).is_file()]
assert not missing, f"引用的卡片文件不存在: {missing}"

for d in movies:
    d["link"] = "outputs/" + d["file"]

payload = json.dumps(movies, ensure_ascii=False, separators=(",", ":"))
# 防止内容里出现 </script> 提前闭合脚本标签
payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

count = len(movies)
year_min = min(d["year"] for d in movies)
year_max = max(d["year"] for d in movies)
date_first = movies[0]["date"]
date_last = movies[-1]["date"]

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>经典电影推荐 · __COUNT__ 部归档</title>
<style>
  :root{
    --bg:#0d0f12; --panel:#151920; --panel2:#1d222c; --line:#2e3646;
    --tx:#eef1f6; --tx2:#b7bfcd; --tx3:#7c8698;
    --acc:#d9a441; --acc2:#7fa88c; --warn:#e07a5f;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    background:var(--bg); color:var(--tx);
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    line-height:1.7; padding:48px 20px 80px;
  }
  .wrap{max-width:1120px;margin:0 auto}
  .kicker{font-size:11.5px;letter-spacing:.24em;color:var(--tx3);text-transform:uppercase;margin-bottom:12px}
  h1{font-size:36px;line-height:1.25;letter-spacing:-.02em;margin-bottom:10px}
  h1 em{font-style:normal;color:var(--acc)}
  .lede{color:var(--tx2);font-size:15px;max-width:720px;margin-bottom:26px}
  .lede b{color:var(--tx);font-weight:600}
  .stats{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:30px}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:120px}
  .stat b{display:block;font-size:21px;color:var(--acc);line-height:1.25}
  .stat small{color:var(--tx3);font-size:11.5px;letter-spacing:.03em}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:22px}
  input[type=search],select{
    background:var(--panel);border:1px solid var(--line);color:var(--tx);
    border-radius:9px;padding:10px 14px;font-size:14px;outline:none;font-family:inherit;
  }
  input[type=search]{flex:1;min-width:220px}
  input[type=search]:focus,select:focus{border-color:var(--acc)}
  input::placeholder{color:var(--tx3)}
  button{
    background:var(--panel2);border:1px solid var(--line);color:var(--tx2);
    border-radius:9px;padding:10px 16px;font-size:13.5px;cursor:pointer;font-family:inherit;
    transition:.15s;
  }
  button:hover{border-color:var(--acc);color:var(--acc)}
  .hint{font-size:12.5px;color:var(--tx3);margin-bottom:20px}
  .hint b{color:var(--tx2);font-weight:600}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:14px}
  .item{
    display:block;background:var(--panel);border:1px solid var(--line);
    border-radius:13px;padding:18px 18px 16px;text-decoration:none;color:inherit;
    transition:.16s;position:relative;overflow:hidden;
  }
  .item:hover{border-color:var(--acc);transform:translateY(-2px);background:var(--panel2)}
  .item::after{content:"↗";position:absolute;right:16px;top:15px;color:var(--tx3);font-size:14px}
  .item:hover::after{color:var(--acc)}
  .n{display:inline-block;font-size:11px;letter-spacing:.1em;color:var(--acc);
     border:1px solid rgba(217,164,65,.35);border-radius:5px;padding:2px 7px;margin-bottom:11px}
  .cn{font-size:19px;font-weight:600;line-height:1.35;margin-bottom:3px;padding-right:26px}
  .en{font-size:12px;color:var(--tx3);font-style:italic;margin-bottom:12px;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .line{font-size:12px;color:var(--tx2);margin-bottom:8px}
  .line span{color:var(--tx3)}
  .sc{font-size:12.5px;color:var(--acc2);margin-bottom:9px;letter-spacing:.01em}
  .note{font-size:12px;color:var(--tx3);line-height:1.6;
        display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .empty{color:var(--tx3);padding:40px 0;text-align:center;font-size:14px;display:none}
  footer{margin-top:52px;padding-top:24px;border-top:1px solid var(--line);
         font-size:12.5px;color:var(--tx3);line-height:1.9}
  footer a{color:var(--acc2);text-decoration:none}
  footer a:hover{text-decoration:underline}
  footer b{color:var(--tx2);font-weight:600}
  @media(max-width:600px){body{padding:30px 14px 60px}h1{font-size:28px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="kicker">Daily Classic Film · Archive</div>
  <h1>经典电影推荐 · <em>__COUNT__ 部</em>归档</h1>
  <p class="lede">每天一部公认的经典，<b>不剧透</b>。每张卡片自带剧情梗概、亮点、推荐理由、
     批评与版本提醒，<b>零外链、零依赖</b>——点开就能读，不需要联网补资源。</p>

  <div class="stats">
    <div class="stat"><b>__COUNT__</b><small>期 · 无重复</small></div>
    <div class="stat"><b>__YMIN__–__YMAX__</b><small>影片年份跨度</small></div>
    <div class="stat"><b>__DFIRST__</b><small>起 → __DLAST__</small></div>
    <div class="stat"><b>0</b><small>剧透 · 外部依赖</small></div>
  </div>

  <div class="bar">
    <input type="search" id="q" placeholder="搜片名 / 外文名 / 年份 / 关键词…" autocomplete="off">
    <select id="sort">
      <option value="n">按期号</option>
      <option value="year-asc">按年份（早→晚）</option>
      <option value="year-desc">按年份（晚→早）</option>
      <option value="douban">按豆瓣分</option>
    </select>
    <button id="random" type="button">随机抽一部</button>
  </div>
  <div class="hint" id="hint">共 <b>__COUNT__</b> 部 · 点击任意卡片打开完整推荐</div>

  <div class="grid" id="grid"></div>
  <div class="empty" id="empty">没找到——换个关键词试试。</div>

  <footer>
    <b>关于这个归档：</b>44 期推荐由一个每日自动化任务连续生成，选片避开所有已推荐影片，
    评分与奖项逐期现查，并明确标注口径差异（如不同快照、小样本、老片回溯分）。
    每张卡片都列出批评意见与版本陷阱，不替影片辩护。<br>
    <b>看之前：</b>建议别先补历史背景或人物传记——那类"科普"长文往往把后半段一次说光。
    留一个完整下午，原速、大屏。<br>
    数据源 <code>movies.json</code> · 索引由 <code>build_index.py</code> 生成 ·
    <a href="https://github.com/zhonghugo/classic-movie-recommendations">GitHub 仓库</a>
  </footer>
</div>

<script>
const MOVIES = /*__MOVIES__*/;
const grid = document.getElementById('grid');
const q = document.getElementById('q');
const sort = document.getElementById('sort');
const hint = document.getElementById('hint');
const empty = document.getElementById('empty');

function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function douban(d){
  const m = /豆瓣\s*([\d.]+)/.exec(d.scores || '');
  return m ? parseFloat(m[1]) : 0;
}
function noteShort(s){
  let t = String(s || '').replace(/[；;]/g, ' · ').replace(/\s+/g, ' ').trim();
  return t.length > 90 ? t.slice(0, 90) + '…' : t;
}
function render(){
  const kw = q.value.trim().toLowerCase();
  let list = MOVIES.filter(d => {
    if(!kw) return true;
    return [d.title_cn, d.title_en, d.year, d.n, d.scores, d.note].join(' ').toLowerCase().includes(kw);
  });
  const mode = sort.value;
  if(mode === 'year-asc')  list.sort((a,b) => a.year - b.year || a.n - b.n);
  if(mode === 'year-desc') list.sort((a,b) => b.year - a.year || a.n - b.n);
  if(mode === 'douban')    list.sort((a,b) => douban(b) - douban(a) || a.n - b.n);
  if(mode === 'n')         list.sort((a,b) => a.n - b.n);

  grid.innerHTML = list.map(d => `
    <a class="item" href="${encodeURI(d.link)}" title="打开第 ${d.n} 期：${esc(d.title_cn)}">
      <span class="n">第 ${d.n} 期</span>
      <div class="cn">${esc(d.title_cn)}</div>
      <div class="en">${esc(d.title_en || '—')}</div>
      <div class="line"><span>${d.year} 年</span> · 推荐于 ${d.date}</div>
      <div class="sc">${esc(d.scores || '—')}</div>
      <div class="note">${esc(noteShort(d.note))}</div>
    </a>`).join('');
  empty.style.display = list.length ? 'none' : 'block';
  hint.innerHTML = `共 <b>${list.length}</b> 部 · 点击任意卡片打开完整推荐`;
}
q.addEventListener('input', render);
sort.addEventListener('change', render);
document.getElementById('random').addEventListener('click', () => {
  const d = MOVIES[Math.floor(Math.random() * MOVIES.length)];
  window.location.href = encodeURI(d.link);
});
render();
</script>
</body>
</html>
"""

out = (TEMPLATE
       .replace("__COUNT__", str(count))
       .replace("__YMIN__", str(year_min))
       .replace("__YMAX__", str(year_max))
       .replace("__DFIRST__", date_first)
       .replace("__DLAST__", date_last)
       .replace("/*__MOVIES__*/", payload))

(ROOT / "index.html").write_text(out, encoding="utf-8")
print(f"index.html 已生成：{count} 条 / {len(out.encode('utf-8'))} bytes")
