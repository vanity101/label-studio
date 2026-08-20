# Contract: 智源机器人视频标注（侍出入口）

本轮按 `docs/harness/exec-plans/active/label-studio-annotation-ux-runtime.md` 交付。叠加在 overlay 与 UX 之上，不取代它们。

只闭合「页面实际加载的前端」。禁止重写 Label Studio 核心，禁止完整 clone，禁止改多视角 XML，禁止把 Vite ESM 改名为 Webpack 的 `main.js`。

## Deliverables

- 官方镜像 HTML 改为 `type=module` 加载 Vite dist 的真实入口（manifest / hash 名保持 Vite 命名）
- overlay Dockerfile 仍 `FROM heartexlabs/label-studio`，把 Vite dist、manifest、上述 HTML 打进自建镜像
- 正在监听的 `http://localhost:8080/` 使用该镜像
- 本文件对应的 eval；Playwright 独立点 `Place` 切段
- 上一轮 overlay / annotation / UX Python eval 仍绿

## Verification

- overlay：`python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py`
- `python3 docs/harness/evals/test_robot_video_annotation.py`
- `python3 docs/harness/evals/test_robot_video_ux.py`
- 本轮：`python3 docs/harness/evals/test_robot_video_ux_runtime.py`
- 前端单测（有 bun）：`cd web && bun test --dom libs/editor/src/tags/control/__tests__/timelineClickToSpan.test.js`
- Playwright：打开 `http://localhost:8080/`，登录或注册后进入单视角任务，播放头到 N，点 `Place`，Regions 为 start=1 end=N，Place 不保持选中
- 上游 Cypress / 全仓 build：不是本轮通过条件

## Hard thresholds

- 上述三条既有 Python eval 全绿；本轮 runtime eval `pass_rate >= 0.8` 且无 Critical
- `check_overlay.py` 退出码 0
- `http://localhost:8080/` 可见登录页或项目页，不是空白 document
- 该实例实际侍出的应用 JS（manifest 指向的 Vite hash 文件，不是 Webpack `main.js`）含 `handleLabelClick` 与 `nextClickSpan`
- 页面应用入口是 `type=module`；没有把 `runtime.js` + `vendor.js` + 经典 `main.js` 当作应用入口
- overlay Dockerfile 仍 `FROM heartexlabs/label-studio`；没有 `cp` Vite 文件覆盖 Webpack `main.js` 的构建步骤
- Playwright 点 `Place`：start=1、end=当前播放头，Place 不保持选中
- 不改 `configs/multi-view.xml`

## 合同写死的边界行为

- 禁止把 Vite 入口改名为 / 覆盖成 Webpack `main.js`
- 禁止把「请用户强制刷新 / 请用户点 Place」当 Verify
- 本轮不新开侧栏改名、废弃锁定、Manual 拖拽、多视角的 Playwright 全量回归；那些仍以既有 Python eval 绿为约束
- 切段公式与 UX 合同相同（帧从 1 起算）

## Failure behavior

- 无法对齐侍出时返回明确错误（HTML 仍 Webpack、静态 404、白屏、入口不含切段字符串、点 Place 仍是官方单帧）
- 禁止完整 clone、禁止改多视角 XML、禁止重写核心、禁止编造手册没有的质检规则
