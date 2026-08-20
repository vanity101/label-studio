# Problem

UX 源码与 Python eval 已 PASS（`docs/harness/reviews/robot-video-ux-2026-08-17.md`），但标注员路径未闭合。运行时评审已 FAIL（`docs/harness/reviews/robot-video-ux-runtime-2026-08-17.md`）。事实如下，不要再猜：

- 官方镜像 `heartexlabs/label-studio:latest` 的 Django HTML 加载 Webpack 经典脚本：`/react-app/runtime.js` + `vendor.js` + `main.js`。
- 仓库 `bun run build` 产出 Vite hash 包；点标签切段逻辑在这份 Vite 包里。
- Django 模板不会去加载 Vite hash 包。标注页仍是官方「先选标签再画」：点 Place 保持选中，区间变成单帧。
- 用 Vite ESM 覆盖官方 `main.js` 会导致 `http://localhost:8080/` 白屏（已发生，已从镜像层恢复官方文件）。禁止再这样做。
- Overlay Dockerfile 已 `FROM heartexlabs/label-studio:latest`，并拷了 Vite `web/dist`，但官方 HTML 仍走 Webpack，切段进不了侍出入口。
- Playwright 现已可用。本轮必须独立核验。不能让人去点页面、强制刷新、或自己审阅当 Verify。

本轮**只闭合侍出入口**：让点标签切段出现在正在跑的单视角标注页。不新开产品交互。不交付 Manual 拖拽。不覆盖上一轮 overlay / UX 产品规格。

叠加关系：`label-studio-annotation.md`（overlay）与 `label-studio-annotation-ux.md`（前端交互）仍有效。本文件只补「正在侍出的页面必须真正加载含切段逻辑的前端」。

# Users and Context

- **标注员**：打开本机 `http://localhost:8080/` 上正在跑的自建镜像，进入已贴单视角模板的任务，把播放头停在阶段结束处，点顶部 `Place`（或其它阶段标签）即生成区间。他们不会去仓库里跑 Python eval，也不会手动替换静态文件。
- **项目负责人**：仍用上一轮 overlay 建项目、贴 `configs/single-view.xml`。本轮不改多视角 XML，不改账号 / 领取任务。
- **本仓库 Agent**：先写完成合同，再改侍出路径；独立用 Playwright（或等价无头浏览器）核验；Reviewer 落盘之后才进人确认。禁止完整 clone、禁止重写 Label Studio 核心、禁止把 Vite 文件改名为 Webpack 的 `main.js`。
- **人**：只确认验收。不代替本轮 Verify。

已确认、不要再猜：

1. 切段公式与 UX 规格相同：第一段 start=1、end=播放头 N；点标签即出现在 Regions；点完后该标签不保持「先选再画」的选中态。
2. 自建镜像必须仍是「官方镜像 + 改过的前端」，不是新栈。
3. 本轮不交付侧栏改名回归、废弃锁定回归、Manual 拖拽、多视角。那些仍以源码 / Python eval 绿为叠加约束，不当成本轮新开交互。
4. 容器现状（交接）：`zhiyuan-ls` 在 8080，镜像 `zhiyuan-label-studio:ux`，数据卷 `/Users/vanity/Public/mydata`。白屏已恢复；切段仍未进侍出入口。

# Deliverables

全部落在「侍出入口对齐 + 自建镜像仍基于官方发行版 + 独立运行时核验」上。不重写 Label Studio 产品，不新开标注交互。

1. **本文件**：运行时侍出入口执行计划（产品 / 工程边界层）。
2. **完成合同**：由后续 Coder 写入 `docs/harness/evals/`（建议新开 runtime 合同，不要把「docker build 标成 ENV 即可」再当成可通过）。合同未写之前不改镜像 / HTML / 静态侍出路径。
3. **自建镜像的侍出对齐（方向 A）**：官方镜像里 Django 实际吐给浏览器的 HTML，改为 `type=module` 加载本仓库 Vite dist 的真实入口（manifest / hash 名保持 Vite 自己的命名）。页面因此加载到含切段逻辑的包。禁止把 Vite 文件改名为 Webpack 的 `main.js`。禁止继续让首页走 `runtime.js` + `vendor.js` + 经典 `main.js` 作为应用入口。
4. **Dockerfile 约束**：仍 `FROM heartexlabs/label-studio`（当前 overlay Dockerfile 的官方基础镜像）。构建说明仍是「官方镜像 + 改过的前端」。不要从零打全栈新镜像替代官方发行版。
5. **独立核验**：Playwright（或等价无头浏览器）打开正在跑的实例，断言首页非白屏、实际加载的 JS 含切段逻辑、单视角任务上点 `Place` 切出 start=1 end=N。人点页面不算核验。
6. **上一轮检查仍绿**：overlay 检查、annotation eval、UX Python eval 不得被本轮侍出改动打红。

稳定产品摘要仍用已有文件，本轮不另开产品能力：

- `docs/harness/product-specs/zhiyuan-robot-video-annotation.md`
- `docs/harness/product-specs/zhiyuan-robot-video-ux.md`

# Success Criteria

以下任一项不满足，本轮即未完成。核验必须由 Agent / Reviewer 独立完成，不能把「请用户打开页面」当作通过。

- **首页不是白屏**：`http://localhost:8080/` 可见登录页或项目页（有可识别的 Label Studio 界面，不是空白 document）。
- **实际加载的 JS 含切段逻辑**：浏览器为该页请求并执行的应用脚本中，含 `handleLabelClick` 与 `nextClickSpan`。只存在于仓库源码、Vite 未侍出的 hash 包、或未被 HTML 引用的文件里，不算。
- **点标签切段出现在单视角标注页**：打开已贴当前 `configs/single-view.xml` 的单视角任务；播放头在第 N 帧；点顶部 `Place`；Regions 出现一段 start=1、end=N，标签名为 `Place`；`Place` 不保持选中（不再表现为官方「先选再画」）。
- **上一轮仍绿**：`python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py` 退出码 0；`python3 docs/harness/evals/test_robot_video_annotation.py` 全绿；`python3 docs/harness/evals/test_robot_video_ux.py` 全绿。
- **镜像身份**：overlay Dockerfile 仍 `FROM heartexlabs/label-studio`；自建镜像仍是官方发行版加改过的前端，不是新栈。
- **禁止项未再发生**：没有把 Vite ESM 文件改名为 / 覆盖成 Webpack 的 `main.js`；没有因此制造新的白屏。

硬门槛草案（写入合同时须保留）：约定的运行时检查全绿；Python eval 无 Critical。任一项不达标则本轮失败。

# Out of Scope

- 新开产品交互（侧栏改名、废弃锁定、Regions 排序、细致度 / 动作序列搬位等）。那些已在 UX 规格里，本轮只要求它们的 Python eval 仍绿，不要求本轮 Playwright 全量回归。
- Manual 拖拽改 Regions 列表顺序。
- 改多视角 XML；验收三路视频。
- 完整 clone 上游大仓；从零自研播放器 / 时间轴内核；重写 Label Studio 核心。
- 用根目录 `docker-compose.yml` / 根目录全栈 Dockerfile 替换「官方镜像 + 前端」这条线。
- Django 业务逻辑 / 保存 / 导出 / 账号体系改造。本轮允许的后端触及仅限：让官方镜像的 HTML 与静态入口能 `type=module` 加载 Vite dist（侍出合同），不是改标注数据模型。
- 把「请强制刷新 / 请用户点 Place」当成 Verify。
- 覆盖或作废 overlay / UX 规格、已 PASS 的源码评审、已 FAIL 的运行时评审（后者由本轮闭合，不假装没发生）。

# Existing Building Blocks

优先复用，禁止另起一套标注产品或另起一套前端栈：

- **已实现的切段源码**：编辑器里点标签切段已接到时间轴标签点击；Vite 构建会打进 Vite dist。本轮要侍出的是这份能力，不是重写切段公式。
- **本仓库已是 Vite 侍出合同**：仓库内 Django HTML 已按 `type=module` 加载 `manifest_asset` 后的入口，而不是 Webpack 三文件。官方发行镜像仍停在 Webpack 三文件。对齐时复用仓库已有的 Vite HTML / manifest / dist 侍出方式，不要发明第三套加载协议。
- **Overlay Dockerfile**：已 `FROM heartexlabs/label-studio:latest`，已用 bun 打 Vite dist。缺的是官方 HTML 仍加载 Webpack。在这条 Dockerfile 上补齐侍出，不要改成从源码重建整个官方后端。
- **根目录生产 Dockerfile 的静态收集方式**（`web/dist` + manifest + collectstatic）：可参考「Vite 产物如何进入 Django 静态树」，但最终运行时基座仍必须是官方镜像，不能把本轮做成「用根目录 Dockerfile 打全新镜像」。
- **现有 overlay 单视角模板**：顶部阶段标签 + 「废弃」Choices。项目 Labeling Setup 须已贴这份模板，本轮不改 XML。
- **Python eval / overlay 检查**：上一轮合同仍是回归门禁。
- **Playwright MCP**：本轮独立 UI 核验入口。不要再把不可用的 Playwright 当借口交给人点。
- **运行中实例**：`zhiyuan-ls` / `zhiyuan-label-studio:ux` / 数据卷 `/Users/vanity/Public/mydata`。闭合侍出后应让该路径上的标注员看到切段，而不是另起一套无人用的预览服。

# High-Level Approach

**本轮选定方向 A，不选 B。**

- **A（选定）**：连同官方 HTML 一起改为 `type=module` 加载 Vite dist。浏览器拿到的应用入口是 Vite 模块图（含切段逻辑的那份构建产物）。禁止把 Vite 文件改名为 Webpack 的 `main.js`。
- **B（本轮明确不走）**：把切段打进 Webpack 实际加载的 `runtime.js` + `vendor.js` + `main.js` 包。仓库前端构建已是 Vite，工作区没有可复用的 Webpack 打编辑器包路径；在发行版压缩包上补丁或把 Vite 文件冒充 Webpack 入口，正是上一轮白屏事故。

落地原则（产品 / 镜像层，不写死函数）：

1. **先合同后改侍出**：Coder 把运行时完成合同写入 `docs/harness/evals/`，硬门槛包含首页非白屏、实际加载脚本含切段字符串、Playwright 点 `Place` 切段。没有合同不改 HTML / Dockerfile / 容器静态文件。
2. **只改侍出合同，不改标注内核**：切段行为继续来自已有编辑器改动 + Vite 构建。本轮把官方镜像里「页面加载哪份 JS」改成与这份构建一致。
3. **HTML 与产物一起换加载协议**：官方镜像当前 HTML 仍按经典脚本拉 Webpack 三文件。改为与本仓库 Vite 一致：`type=module` 指向 Vite dist 的真实入口（hash / manifest 由 Vite 构建产生，保持原名）。同步必要的 CSS / 附属模块，使登录页与项目页能启动。不要只拷 dist 却让 HTML 继续引用 Webpack；也不要只改 HTML 却让请求落到不存在的 Vite 文件。
4. **静态树必须被官方镜像真正侍出**：仅把 `web/dist` 放进镜像、Django 仍从 Webpack 静态根读文件，等于没换。需要对齐官方镜像已有的静态入口（页面请求的 URL → 磁盘上的 Vite 文件），包括 manifest 若 HTML 依赖它解析入口。参考根目录镜像如何把 Vite 产物收进静态树，但基座保持官方发行镜像。
5. **覆盖面最小化**：允许覆盖官方镜像中负责加载前端的 HTML（以及为解析 Vite 入口所必需的静态映射）。禁止整棵替换 `label_studio/` 业务、禁止完整 clone、禁止改播放器 / 时间轴内核、禁止改多视角 XML。
6. **重建并替换正在跑的标注入口**：按 overlay Dockerfile 重建自建镜像，让 `localhost:8080` 上标注员走的就是新侍出路径。不要再在运行中容器里手工 `cp` 单个 JS 文件当交付。
7. **独立核验后再进人**：Playwright 打开首页与单视角任务；另用页面实际请求到的脚本内容断言切段字符串。Reviewer 按合同复跑。未恢复可用、未写评审之前，不把「请强制刷新」发给人。

# Risks

已证实、按事故处理，不再当未知：

- **Webpack HTML + Vite 文件同名覆盖 = 白屏**。官方 HTML 按经典脚本执行 `main.js` 时，ESM Vite 包无法启动。本轮若再把 Vite 入口改名为 Webpack `main.js`，视为直接失败。
- **只拷 Vite dist、不改 HTML = 切段对标注员不可见**。Python eval 仍会绿。合同必须卡侍出入口，不能再把 docker build 标成 ENV 就过关。
- **人点页面不是 Verify**。上一轮把强制刷新交给人，违反「Agent 跑检查」。本轮 Playwright 可用，必须用它（或等价无头）独立核验。

仍要防：

- **HTML 改成 module 但静态 404**：入口、CSS、或 Vite 附属 chunk 没进官方镜像的侍出路径 → 白屏或半残页。成功标准里的「不是白屏」就是这道闸。
- **只改了构建机上的一份镜像，8080 仍跑旧层**：标注员路径以正在监听的实例为准。核验必须打 `http://localhost:8080/`（或合同写明的同一实例），不能只看 `docker build` 成功。
- **官方镜像内部静态布局与本仓库 Vite 布局不一致**：路径前缀、manifest 位置、是否经过收集静态文件，可能与根目录全栈镜像不同。对齐失败时报告差距，禁止靠改名冒充 Webpack 入口绕过去。
- **CSP / nonce / 经典脚本假设**：官方页若仍插入 Webpack `runtime.js`，同时再加 module 入口，可能双启动或冲突。应用入口应只有 Vite module 这一套，不要两套并存。
- **缓存**：浏览器或服务工人可能仍拿旧 `main.js`。独立核验应看页面实际网络请求，而不是仓库磁盘。不要把「请用户强刷」当修复。
- **范围膨胀**：借机重写 Django、换全栈镜像、或把 UX 未闭合的侧栏 / 废弃做成新交互。本轮失败条件是侍出未闭合，不是产品功能清单没做完。
- **字面量与模板**：单视角仍须已贴当前 XML（含顶部「废弃」）。本轮不改 XML；未贴模板导致切段不触发，是环境准备问题，应在核验步骤里先确认，不因此改多视角或发明新标签。

# Suggested Verification

完成合同由后续 Coder 写入 `docs/harness/evals/`。本轮规格不假装运行时已绿。

建议合同至少覆盖：

- **首页**：无头打开 `http://localhost:8080/`，可见登录或项目界面；`document` 不是空壳白屏。
- **侍出入口**：从该页实际发出的脚本请求（不是仓库 `web/dist` 目录列举）中，应用入口为 `type=module` 的 Vite 产物；响应体含 `handleLabelClick` 与 `nextClickSpan`。同时断言页面没有把 Webpack 三文件当作应用入口，也没有把 Vite 文件侍出成 Webpack `main.js` 文件名来骗过检查。
- **切段冒烟（Playwright）**：登录（或沿用已登录会话 / 数据卷已有用户）→ 打开单视角任务 → 播放头到第 N 帧 → 点 `Place` → Regions 出现 start=1、end=N；`Place` 不保持选中。N 取页面可见的当前帧，不要写死某一个发行版样例帧号当唯一合法值。
- **回归**：`check_overlay.py`、`test_robot_video_annotation.py`、`test_robot_video_ux.py` 全绿。
- **Dockerfile**：overlay 文件仍 `FROM heartexlabs/label-studio`；构建说明仍是官方镜像 + 改过的前端。
- **硬阈值草案**：上述运行时与回归检查全绿；eval 若有 pass_rate，建议 ≥ 0.8 且无 Critical。白屏、入口不含切段字符串、点 Place 仍是官方单帧选中，任一项即失败。
- **失败行为**：无法对齐侍出时返回明确错误（HTML 仍 Webpack、静态 404、白屏、Playwright 无法打开 8080）。禁止再用 Vite 覆盖 Webpack `main.js`。禁止把核验推给人。禁止完整 clone、禁止改多视角 XML、禁止重写核心。
