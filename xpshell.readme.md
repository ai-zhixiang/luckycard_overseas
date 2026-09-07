# XP Shell 开发索引 (xpshell.readme.md)

> 为什么有这份文档:hicard.world 的 XP 桌面("XP shell")东西越来越多——
> 桌面图标、开始菜单、Run 对话框、CMD、控制面板、Clippy、彩蛋全挤在
> `xp.js` + `home.html` 里。**改任何入口前先查这张表**,别凭记忆猜,
> 也别只改一处就以为完事(很多入口有双份拷贝)。
>
> 项目根:`/home/ubuntu/luckycardeng`,由 systemd `luckycardeng.service` 托管,
> nginx :80 → uvicorn 127.0.0.1:8000。全站语言:前端 UI 锁死英文,
> 后端报错/账本中文(见"神圣规则")。

---

## 1. 文件地图

| 文件 | 作用 |
|---|---|
| `app/templates/home.html` | XP 壳:桌面图标、任务栏、开始菜单、Run 对话框、托盘。**改它要重启 uvicorn**(Jinja 模板缓存) |
| `app/static/js/xp.js` | 一切交互:窗口管理、Run、CMD、控制面板、主题、Clippy、任务管理器。**大 IIFE**,结尾 `window.XPShell = {...}` 导出 |
| `app/static/js/lucky.js` | Lucky Card 产品 UI:登录/钱包/配额/分享,独立版本号 |
| `app/static/forms/*.html` | 每个"程序"是一个独立 HTML 文档,被 fetch 后 innerHTML 注入窗口 body(见 §3) |
| `app/static/img/*.png` | marchmountain XP 图标包,命名 `xp-xxx_20/32/48.png`(尺寸变体) |
| `app/static/css/xp.css` | 壳样式(窗口/任务栏/开始菜单) |
| `app/static/music/` | 音乐播放器 mp3(曲库在 `app/api/music.py` 的 TRACK_META) |
| `app/api/*.py` | 后端路由,`app/main.py` 注册(prefix `/api`) |

**版本号约定**:JS 在 home.html 以 `xp.js?v=170` 引入 —— **每次改 xp.js 必须 bump**
(当前 v=170)。纯静态文件(forms/img/css)读盘实时,不用重启,但改 home.html 引用的
资源后要 bump 对应 `?v=` 并让用户硬刷新(缓存头号嫌疑)。

---

## 2. 窗口机制 (openWindow)

所有程序统一走 `XPShell.openWindow(id, title, iconHTML, content)`:

- `windows[id]` 已存在 → **只置前,不重开**(id 是单例键,不能两个同 id 窗口并存)。
- `content` 以 `/` 或 `http` 开头 → "Loading…" 后 fetch → innerHTML 注入
  `#xp-win-body-<id>`;`<script>` 会重执行,**运行在桌面页面上下文**(可直接访问
  XPShell、document 等)。否则 content 视为 HTML 字符串直接注入(如回收站玩笑)。
- form 是"塞进既有窗口的碎片",不是顶层文档:CSS 要自包含、尺寸自适应
  (默认窗口约 640×489,移动端全屏,body 可滚动)。普遍写法
  `.xxx-root { position:absolute; inset:0 }` 撑满。
- 每次真开窗会触发 `_clippyTip(id, title)`(仅新开,置前分支早退不触发)。

**窗口内下载**:fetch → blob → `<a download>`,**严禁 `window.location=...`**
(会把整个桌面导航走)。同规则:window 内不要用 `window.open` 干需要留在桌面的事。

---

## 3. 桌面 App 全清单(14 个图标,home.html `.xp-desktop-icons` 单容器)

桌面图标是**单容器纯 CSS flex-wrap 自动换列**(`flex-direction:column; flex-wrap:wrap;
height:calc(100vh-58px)`),加图标 = 照抄一个 `.xp-icon` div 追加即可,**零 JS**。
别写什么 balanceIconColumns。图标间隙用 `style="margin-top:20px"` 分组。

| # | id | 标题 | 入口/内容 | 备注 |
|---|---|---|---|---|
| 1 | `create` | Create Card | 桌面/开始/Run | 主业务,icon xp-ie6 |
| 2 | `gallery` | Gallery | 同上 | forms/card-gallery.html |
| 3 | `mycards` | My Cards | 同上 | forms/my-cards.html |
| 4 | `music` | Music | 同上 | forms/music-player.html |
| 5 | — | Public OpenClaw | **window.open 外链**(无窗口) | http://124.222.215.111:8000 |
| 6 | `ie` | **Internet Explorer** | 桌面/开始/Run/My Computer | forms/internet-explorer.html(2026-09 新) |
| 7 | `recycle` | Recycle Bin | 桌面 | **玩笑组件**:固定 HTML"垃圾桶是空的" |
| 8 | — | Source Code | **window.open 外链** | GitHub ai-zhixiang/luckycard_overseas |
| 9 | `stylizer` | AI Stylize | 桌面/开始/Run | forms/ai-stylizer.html,NSFW 双检 |
| 10 | `culture` | Chinese Culture | 桌面 | 🇨🇳 emoji 图标(用户点名允许),forms/chinese-culture.html |
| 11 | `minesweeper` | Minesweeper | 桌面/开始/Run | forms/minesweeper.html,id 别名 `ms` |
| 12 | `history` | Website's History | 桌面/Run | forms/website-history.html → 读 website-history.md |
| 13 | `mydocs` | My Documents | 桌面/开始/Run/explorer | forms/my-documents.html,真文件浏览器 |
| 14 | `mycomputer` | My Computer | 桌面/开始/Run | forms/my-computer.html,驱动器浏览 |

另有**无桌面图标**的程序(开始菜单/Run/控制面板可达):
`control`(控制面板)、`notepad`、`cmd`(CMD)、`help`、`about`、`sysinfo`(别名 `sys`)、
`taskmgr`(任务管理器,`buildTaskMgrContent`)、`tbp`(任务栏属性)、`windos-dl`(下载提示)。

**开始菜单**(home.html 两列):左列 = Create Card / Gallery / Music / Source Code /
_Win11LPC(window.open /win11lpc)/ **Internet Explorer** / Lucky Wallet / All Programs;
右列 = My Documents / My Pictures(占位)/ My Music(占位)/ My Computer / Control Panel /
Run… / Search(占位)/ Help & Support(占位)。All Programs 项 `.xp-start-all` 无实弹层。

---

## 4. Run 对话框 & cmd start 关键词表 ⚠️ 双份拷贝

**`xp.js` 里有两条几乎相同的 `var routes = {}` 表**,任何新 Run 可启动程序要**两处都加**:

1. `launchByKeyword()` 内(约 L176)—— 供 Run 对话框 + CMD `start <app>` 共用
2. `runCommand()` 内(约 L217)—— 供 Run 对话框(两表历史上不同步过,`start <app>`
   报 not-recognized 就是只改了一处)

格式:`'关键词': ['窗口id', '标题', '标题栏图标HTML', '内容URL或buildXxxHTML()']`

当前关键词(除 URL 直开新标签外):`card create gallery music stylize stylizer mycards
minesweeper ms control notepad cmd help about sysinfo sys history mydocs "my documents"
documents mycomputer "my computer" computer iexplore iexplore.exe ie "internet explorer"`
+ 特判分支:`clippy`、`explorer/explorer.exe`(shell 隐藏→恢复;可见→My Documents)、
`taskmgr/taskman`、`windos/windos.exe/"win dos"`(下载 WinDOS)、`http(s)://…`(新标签)。
未知命令 → "Cannot find" 窗口(建议列表要同步加新词)。

---

## 5. CMD 窗口命令(_initCmdWindow 内 run())

`dir`(伪目录)、`cls`、`ver`(→ Lucky Card [Version 16.1145.2600])、`date`、`time`、
`echo`、`color`、`help`、`exit`、`start <app|URL>`(走 launchByKeyword 表)、
`tasklist`(XP 风格进程表)、`taskkill /PID n | /IM name`(+`tskill` 别名;
系统进程无 /F 拒绝:`Access denied: The process "…" could not be terminated.`;
有 /F → `endSystemProcess` → **BSOD**;explorer.exe 无 /F 也杀,=隐藏壳)、
`poweroff`/`shutdown`(关机动画)、`rmcards`(彩蛋,慎)、`card/gallery/music/minesweeper/…`
(直接开 app)、`taskmgr`。

完整命令与精确文案见技能 `references/xp-cmd-console.md`。

---

## 6. Control Panel(openCPItem)

`buildControlPanelHTML()` 渲染分类网格;`openCPItem(action)` 查两张 map:
`titles{}`(面包屑)+ `menu{}`(action→返回 HTML 的函数;部分有自缓存 `_html` 怪癖)。
加子页 = `titles` + `menu` 都加 + 网格里加可点卡片。

动作:appearance(蓝/银/橄榄绿 **Luna 主题切换**,localStorage `xp-theme`)、network、
sounds、performance、printers、accounts、datetime、accessibility、security、
**clippy**(Clippy 开关,走 /api/prefs 服务端持久化)。面板顶部有 ◀ Back(backToControlPanel)。

---

## 7. Clippy(Office Assistant,2026-09)

- 触发:`_clippyTip(id,title)` 挂在 openWindow 新开分支,每 app **3 条硬编码英文台词**
  随机 1 条,15–20s 自动消失。**零成本**:禁 DeepSeek、禁扣点。
- 台词池 `_clippyTips`/`_default`(新 app 记得加 3 条)。
- 关闭:托盘回形针右键菜单;重开:控制面板 → Clippy Assistant 或 Run `clippy`。
- 开关存服务端 `/api/prefs`(`data/prefs.json`,identity keyed),不用 localStorage。
- 素材:真实 Clippy sprite(`app/static/img/clippy-*.png`,从 clippyjs npm 抠出),
  不要手绘 SVG。提取配方见技能 references/xp-shell-wiring.md。

---

## 8. 彩蛋清单(用户是彩蛋狂,别删)

| 彩蛋 | 触发 |
|---|---|
| BIOS 启动动画 | 每次进站(flavor 文本是神圣的,别"修正",见 §11) |
| Run `clippy` | 手动召唤大眼夹 |
| Run `windos` / CMD `start windos` | 下载 WinDOS 镜像(My Computer E: 盘也有) |
| Run `history` | 网站编年史窗口 |
| 音乐播放器双击标题 | Rickroll(Astley,曲库最后一首) |
| CMD `taskkill /F` 系统进程 | BSOD |
| 回收站 | "The Recycle Bin is empty. Your luck never goes to waste." |
| CMD `rmcards` / `poweroff` | 见 xp.js 源码(先读再跑) |
| My Computer A: 盘 | 软驱报错"设备未就绪";E: 盘 = WinDOS Setup CD |
| Boot 后随机 BSOD 玩笑 | LUCK_OVERFLOW_ERROR(站点自身流程,不是 bug) |

---

## 9. 主题 / 窗口 / 系统

- Luna 主题 `setTheme('blue'|'silver'|'olive')`,桌面 chrome 配色随 localStorage `xp-theme`。
- 窗口:拖动 startDrag/scheduleDrag/applyDragPosition、最小化 minimizeWindow、
  最大化 toggleMaximize、关闭 closeWindow;每窗一个稳定 pid(3000+rand),
  **taskmgr 列表每 2s 随机刷新,别拿它匹配 taskkill**。
- 托盘右键菜单 showTaskbarMenu(右击弹出:右键释放会触发 click,mousedown 关闭器
  必须 `e.button !== 0` 早退)。
- 键盘:Alt+R = Run(Win+R 被浏览器占了)。
- shell 可隐藏(`hideShell`,explorer.exe 被杀时)+ 恢复(`restoreShell`)。
- 关机会话:logOff / shutDown / doRestart / doStandby / showShutdownDialog / bsodRestart。

---

## 10. 神圣规则(用户截图逐条盯,违反必被骂)

1. **前端 UI 全英文**;后端 HTTPException / 账本中文。xp.js 无 zh 字典,别搞半吊子 i18n。
2. **桌面/窗口 UI 图标禁 emoji、禁 SVG 占位**,用 marchmountain XP 包
   (`_32` 桌面 / `_20` 标题栏)。唯一例外:Chinese Culture 的 🇨🇳(用户点名);
   窗口正文内容里现存的 emoji(⚠️💻❓ℹ️)是历史遗留,新代码别加。
3. 字体栈 Tahoma 在前(`'Tahoma','SimSun','宋体','Segoe UI',sans-serif`),别写 Segoe 在前。
4. **flavor 文本神圣**:`Version 16.1145 (Build 2600)`、BIOS 里
   `Open(R) AI(TM) GPT v1.0`、`LuckyCard SSD 512GB` 等一律别"修正"。
5. 货币单位 **pts**;`Guest · 0 pts`。
6. 桌面图标任意加(自动换列);但**位置类需求先截图确认再改**,别瞎猜第二次。
7. 回形针图标=真实素材;别手绘。
8. 改 JS:inline onclick 里嵌 `XPShell.fn('arg')` 的 `\'` 在反复 patch 后会坏,
   用 class + document 级事件委托。改完 `node --check`。
9. 改 .py 用 `python -m py_compile`;python 报错信息留中文。
10. 有中文泄漏?`grep -nP '[\x{4e00}-\x{9fff}]'` 查 user-facing JS/forms(应为 0)。

---

## 11. 修改 → 上线流程

1. 改 JS → bump home.html 里 `xp.js?v=N`(和 lucky.js 同理)。
2. 改 forms/img/css(纯静态)→ 直接生效;但 home.html 里的引用要 bump `?v=`。
3. 改 home.html 或任何 .py → **重启服务**:
   `P=$(ss -tlnp | grep ':8000 ' | grep -oP 'pid=\K[0-9]+'); kill $P`
   (systemd 自动拉起新 pid,1–3s;**别**手起 uvicorn/nohup 抢 8000)。
   日志:`journalctl -u luckycardeng.service -n 100 --no-pager`。
4. 验证:`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/` → 200;
   `curl -s http://127.0.0.1:8000/ | grep -o 'xp.js?v=[0-9]*'`。
5. 让用户**硬刷新**(缓存头号嫌疑;图标错乱/时钟 00:00 = 旧 HTML 缓存)。
6. 提交 GitHub(用户问"啥时候更新 GitHub"时):见 hicard-world-dev 技能 push 卫生
   (`.env`、`data/`、zip/exe、stylized、uploads、WinDOS.bak.zip 永不提交)。

---

## 12. 后端 API 模块速查(app/api/)

| 文件 | 职责 | 数据文件 |
|---|---|---|
| auth.py | 登录/身份,`identity_from(request)` → `ip:<addr>` / `user:<id>` | — |
| wallet.py | Lucky Point 钱包($1=100pts,整数美元充值) | data/quota.json |
| cards.py | 卡片 CRUD + 分享页 + DeepSeek 写诗(prompt/诗**中文勿动**) | data/… |
| payment.py / paypal.py | PayPal 充值回调(PayPal recharge:<uid>) | — |
| culture.py | Chinese Culture 43 主题日轮换,维基+DeepSeek 双语 | 内存缓存 |
| music.py | 曲库 TRACK_META + `/api/music/play` | app/static/music/ |
| prefs.py | 每身份设置(如 clippy 开关),PUT 免费不计费 | data/prefs.json (0600) |
| userfiles.py | My Documents 文件浏览器(30 文件/50MB 限额,超限 1h 清;10s 20 创建封 IP 30 天) | data/userfiles/<sha1[:24]>/ |
| static_manager.py | 静态浏览(My Computer C: 盘)/ 上传;stylized 目录对游客隐藏 | app/static/ |

`/api/static/list?path=` 是公开只读的站点文件浏览 —— My Computer 的 C: 盘数据源。
计费扣点:诗 10 / 识图 10 / 画图 15 / 风格化 15,每 IP 每日 3 次免费。

---

## 13. 相关技能与深层手册

本文件是"速查索引";详细工作流在 agent 技能里:
- `hicard-world-dev`(伞技能):语言规则、部署、GitHub push、CJK 审计
  - `references/xp-shell-wiring.md`:openWindow 扩展点、控制面板、托盘、Clippy 完整配方
  - `references/xp-desktop-ui/SKILL.md`:XP UI 模式(旧独立技能并入)
  - `references/fastapi-backend/SKILL.md`:FastAPI 后端模式(旧独立技能并入)
  - `references/xp-cmd-console.md`:CMD 完整命令+精确文案
  - `references/userfiles-mydocs.md`、`references/music-player.md`
- `windos-os-dev`:WinDOS 引导/内核(WinDOS.bak.zip 在 app/static/)
- 站点编年史(父子创业史):`app/static/website-history.md`(桌面上有图标读它)

> 最后更新:2026-09-07(新增 Internet Explorer 窗口 `ie`;xp.js v170;桌面 14 图标)
