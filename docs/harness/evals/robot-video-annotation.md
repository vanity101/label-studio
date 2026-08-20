# Contract: 智源机器人视频标注（初步能跑）

本轮按 `docs/harness/exec-plans/active/label-studio-annotation.md` 交付 overlay。不改 `label_studio/` / `web/`。

## Deliverables

- 单视角 Labeling Config：一条 `Video` + 一条 `TimelineLabels`，预置 `Static` / `grasp` / `Place` / `End`
- 整段控件（同一配置内，不是第二套时间轴）：细致度、动作序列文本、异常标记
- 2–3 视角配置：结构正确即可，不强制本机播三路
- 单视角示例任务 JSON、官方形状导出夹具、短启动说明
- 配置 / 导出夹具检查脚本与本文件对应的 eval

Overlay 目录：`docs/harness/overlays/zhiyuan-robot-video/`

## Verification

- 上游测试：不是本轮通过条件（稀疏工作区无完整源码）
- eval：`docs/harness/evals/test_robot_video_annotation.py`
- 检查入口：`docs/harness/overlays/zhiyuan-robot-video/check_overlay.py`
- 无 pytest 时：`python3 docs/harness/evals/test_robot_video_annotation.py`

## Hard thresholds

- `python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py` 退出码 0
- `python3 docs/harness/evals/test_robot_video_annotation.py` 全绿（有 pytest 也可用 `python3 -m pytest ... -q`）
- eval pass_rate >= 0.8，且无 Critical 失败
- 单视角配置恰好一条 `TimelineLabels`；预置字面量精确为 `Static`、`grasp`、`Place`、`End`
- **仓库导出夹具**（`examples/annotation-export.json`，裸 `{result:[...]}`）能还原每段 `ranges.start` / `ranges.end` 与标签名，且含两段 `Static`（头尾）。这不是 Label Studio UI Export 整包
- 任意合法标注的形状检查允许：空 `result`、只有整段、部分区间、区间重叠、官方 Export 整包（`annotations[].result`）
- 不出现第二套时间轴冒充细致度
- 工作区 diff 不含 `label_studio/`、`web/` 内核改动

## 合同写死的边界行为

- 缺 `video` 字段的任务：检查脚本拒绝（失败，非静默跳过）
- 空标注（`result` 为空列表）：检查脚本允许（标注员尚未提交或只交整段时不当成配置错误）
- 只有整段、没有时间轴区间：允许
- 两段时间相交：允许（配置不硬互斥）；说明写「默认不重叠」
- 可选 Docker / API 冒烟失败：报告环境，不因此改 Django，也不把本轮判为合同失败

## Failure behavior

- 无法完成时返回明确错误
- 禁止编造手册未写的质检规则、未写的动作词表、或非官方导出字段
- 禁止把细致度做成三个独立标注界面
