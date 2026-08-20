# Contract: 智源机器人视频标注（Regions 扁平拖排序）

本轮按 `docs/harness/exec-plans/active/label-studio-annotation-ux-reorder.md` 交付。叠加在 overlay / UX / runtime 之上，不取代它们。

只补右侧 Regions 扁平拖排序。禁止重写 Label Studio 核心，禁止完整 clone，禁止改多视角 XML，禁止改 ouid / 切段公式，禁止把 Vite ESM 改名为 Webpack 的 `main.js`。

## Deliverables

- 右侧 Regions 上下拖只改名单顺序；start / end / 阶段名不变
- 始终并列：拖到另一行身上不得变成子节点
- 能拖到当前第一行上面，成为新的第一行
- 未拖过时仍是点击 / 创建顺序；拖过之后用拖出来的显示顺序
- 切段「上一标签」仍按创建顺序最后一条
- 本文件对应的 eval；Playwright 在正在跑的单视角页上真的拖一遍
- 上一轮 overlay / annotation / UX / runtime Python eval 仍绿

## Verification

- overlay：`python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py`
- `python3 docs/harness/evals/test_robot_video_annotation.py`
- `python3 docs/harness/evals/test_robot_video_ux.py`
- `python3 docs/harness/evals/test_robot_video_ux_runtime.py`
- 本轮：`python3 docs/harness/evals/test_robot_video_ux_reorder.py`
- 前端单测（有 bun）：`cd web && bun test --dom libs/editor/src/components/SidePanels/OutlinerPanel/__tests__/flatReorder.test.js`
- Playwright：打开 `http://localhost:8080/` 单视角任务，至少三种落点（到另一行上面、到第一行上面、到另一行身上）；再拖乱后点新阶段标签，切段仍按创建顺序
- 上游 Cypress / 全仓 build：不是本轮通过条件

## Hard thresholds

- 上述四条既有 Python eval 全绿；本轮 reorder eval `pass_rate >= 0.8` 且无 Critical
- `check_overlay.py` 退出码 0
- 纯函数：把 `place` 拖到 `static` 前面 → `["place","static","grasp"]`；拖到行上与拖到缝里都不得产生 parent/child
- 切段夹具：名单已被拖乱时，`last_created_end` 仍取最大 ouid 的 end，不取名单最后一行
- Playwright：拖 A 到 B 上面后名单 A 在 B 上，帧不变；拖到第一行上面后该条成为第一行；拖到行身上仍并列（无缩进子节点）
- Playwright：拖乱后再点标签，新段起止按创建顺序最后一条计算
- 不改 `configs/multi-view.xml`
- 没有把 Vite 文件覆盖成 Webpack `main.js`

## 合同写死的边界行为

- 禁止用改 ouid / 创建身份换序
- 禁止拖动时改 start / end / 阶段名
- 禁止把嵌套分组当成交付
- 当次页面顺序即可；不要发明新导出字段
- 禁止把「请用户拖一下」当 Verify

## Failure behavior

- 无法关掉嵌套、插不到第一行上面、切段被拖乱、或上一轮 eval 变红时返回明确错误
- 禁止完整 clone、禁止改多视角 XML、禁止重写核心、禁止再用 Vite 覆盖 Webpack `main.js`
