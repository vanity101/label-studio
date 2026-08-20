# Review Result

FAIL / NEEDS_CHANGES

审查对象：把 UX 前端补丁送进正在跑的 `zhiyuan-label-studio:ux`（容器 `zhiyuan-ls`，数据卷 `/Users/vanity/Public/mydata`），以及「点标签切段」是否已出现在标注员路径上。

这不是对 `docs/harness/reviews/robot-video-ux-2026-08-17.md` 源码 PASS 的否定。那份评审已经写明：合同硬门槛是 Python eval，**标注员真机路径未闭合**；Dockerfile 拷整棵 `web/`，**发行版实际侍出的静态文件是否被替换，未当作已验证**。本文件补的是那条缺口被拿去给人审阅之后的结果。

# Critical Issues

1. **运行中的页面仍走官方 Webpack 入口，点标签切段没有进标注员路径。**  
   官方镜像 `label_studio/templates/base.html` 加载的是经典脚本 `/react-app/runtime.js` + `vendor.js` + `main.js`（Webpack，2026-03-11）。仓库这边 `bun run build` 产出的是 Vite 带 hash 的 `main-*.js` / `src-*.js`，编辑器切段逻辑打在这份包里。Django 模板不会去加载它们。  
   证据：容器内模板仍是三文件 Webpack；标注页表现为 Place 保持选中、区间 132–132（官方「先选再画」）。

2. **把 Vite 入口覆盖到 Webpack 的 `main.js` 上，首页空白。**  
   Coder 在未走新合同、未委派 Reviewer、未独立浏览器核验的情况下，对运行中容器执行了 `cp main-CTBFF60b.js main.js`。官方 HTML 仍按经典脚本加载 `runtime.js` + `vendor.js` + `main.js`，ESM Vite 包无法在这条链上启动。用户报告 `http://localhost:8080/` 一片空白。  
   已从镜像层把官方 `main.js` / `main.css` 拷回容器。这是恢复可用性，不是切段验收通过。

3. **把「请用户强制刷新 / 自己点 Place」当成了 Verify。**  
   `AGENTS.md`：人确认验收；Agent 跑检查、写评审、修复。合同 Verification 虽不要求 Cypress，但规格 Success Criteria 是「点标签 → Regions 出现段」。在 Playwright MCP 不可用时，Coder 没有改用其它独立核验（无头浏览器、容器内静态入口对照、Reviewer），直接把未闭合路径交给人审阅。

# Important Issues

1. Overlay Dockerfile 若用 Vite `main-*.js` 覆盖发行版 `main.js`，会把空白页打进下一张镜像。该 RUN 已从 Dockerfile 去掉，并注明官方 HTML 仍走 Webpack。未重新 `docker build`，镜像 `zhiyuan-label-studio:ux` 仍是「整棵 web/ 覆盖 + 官方 `main.js` 留存」的旧层。
2. 源码侧后来去掉了 `names.get("discard")` 作为切段开关，并加了 `resolveNamedTag`。Python eval / bun 单测绿，但这些改动没有进入正在侍出的 Webpack `main.js`，对标注员不可见。
3. `handoff.md` 在事故前仍写「In progress: 无。Reviewer PASS」，与运行时事实不符。

# Test Gaps

与 2026-08-17 UX 评审相同，且被本次事故证实：

- eval 不打开浏览器、不点 Label、不读 Regions 的 start/end。
- `test_editor_click_to_span_is_wired` 只 grep 源码。
- 没有检查「容器内 `/react-app/main.js` 是否为 Webpack」与「切段代码是否在该文件中」。
- Playwright MCP 当前 `serverStatus=error`，本轮没有替代的 UI 核验。

# Contract Gaps

- 合同把 `docker build` 标成 ENV，不判失败；没有写「侍出的 `/react-app/main.js` 必须含切段逻辑」。结果是 eval 全绿也可以把官方 Webpack GUI 交给人点。
- 规格 Success Criteria 需要真机切段；合同 Verification 没有对应自动化。缺口在源码评审里已写，本轮仍按「eval 绿 = 可给人审阅」执行。

# Suggestions

- 下一轮先写运行时合同：官方镜像 HTML 仍是 Webpack 三文件时，禁止用 Vite ESM 覆盖 `main.js`。可选路径只能是（a）连同 Django 模板一起换成 type=module + Vite dist，或（b）把切段打进 Webpack 实际加载的 editor 包，且用「侍出的 JS 含 `handleLabelClick` / `nextClickSpan`」做硬门槛。
- 独立核验至少一条：无头打开登录后标注页，或对 `/react-app/main.js` 做入口类型断言（Webpack vs Vite）+ 切段字符串。人只确认，不代替这条。
- 未恢复可用、未写评审之前，不把「请强制刷新」发给人。
