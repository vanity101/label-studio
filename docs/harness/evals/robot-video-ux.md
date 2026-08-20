# Contract: 智源机器人视频标注（前端交互）

本轮按 `docs/harness/exec-plans/active/label-studio-annotation-ux.md` 交付。叠加在上一轮 overlay 之上，不取代它。

只做简单单视角。允许改 `web/libs/editor` 编辑器交互；禁止重写 Label Studio 产品、禁止完整 clone 上游历史、禁止改多视角 XML。

## Deliverables

- 点顶部阶段标签即按公式切段，不必再在时间轴上画
- 侧栏选中 Region 后可改标签名（阶段字面量下拉）和 start / end
- Regions 默认按点击 / 创建顺序，先点的在上；不交付 Manual 拖拽调序
- 单视角模板：仅「废弃」与阶段标签同一条顶部栏；点废弃 = 整视频不可用，不产生 `timelinelabels` 区间
- 自建镜像说明：官方镜像 + 本轮改过的前端（不是新栈）
- 本文件对应的 eval 与 overlay 检查扩展

## Verification

- overlay：`python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py`
- 上一轮 eval 仍须绿：`python3 docs/harness/evals/test_robot_video_annotation.py`
- 本轮 eval：`python3 docs/harness/evals/test_robot_video_ux.py`
- 前端单测（有 bun 时）：`cd web && bun test --dom libs/editor/src/tags/control/__tests__/timelineClickToSpan.test.js`
- 上游全量 Cypress / 全仓 build：不是本轮通过条件
- 自建镜像实际 `docker build`：本机依赖不足时报告 ENV，不因此改 Django，也不把本轮判为合同失败（Dockerfile 与 README 必须存在且基于官方镜像）

## Hard thresholds

- 上述两条 Python eval 全绿；本轮 eval `pass_rate >= 0.8` 且无 Critical
- `check_overlay.py` 退出码 0
- 切段公式（帧从 1 起算）：
  - 无上一段、播放头 N → start=1、end=N
  - 上一段结束 N、播放头 M>N → start=N+1、end=M
  - 上一段结束 N、播放头 M≤N → 不拒绝，start=M、end=N（允许重叠）
- 单视角恰好 1 条 `TimelineLabels`；预置阶段字面量精确为 `Static` / `grasp` / `Place` / `End`
- 单视角顶部栏含且仅含一个「废弃」（与 TimelineLabels 同一条栏，出现在 `Video` 之前）；没有「异常」「abnormal」
- 「废弃」导出为整段 `choices`（`from_name=discard`），不是 `timelinelabels` / `ranges`
- 时间轴结果仍是官方 `ranges` + `timelinelabels`
- 不改 `configs/multi-view.xml`
- 变更集不出现「重写整个 Label Studio」的目录级替换；自建镜像说明 `FROM` 官方镜像

## 合同写死的边界行为

- 点废弃之后：不能再切新阶段段、不能再改已有区间的名或帧；已有区间仍可见；仍可提交
- 点废弃不新增时间轴区间
- 播放头早于上一结束帧时点新阶段标签：允许重叠，不截断、不报错
- Manual 拖拽调序：本轮不实现、不验收
- 缺 bun / 无法构建镜像：报告环境，不改 Django，不把本轮判失败（Python 检查仍必须绿）

## Failure behavior

- 无法完成时返回明确错误
- 禁止把废弃写成时间段
- 禁止把细致度做成第二套时间轴
- 禁止完整 clone 上游大仓
- 禁止编造手册没有的质检规则
