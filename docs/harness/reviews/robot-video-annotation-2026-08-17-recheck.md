# Review Result

PASS

复审对象：上轮 `docs/harness/reviews/robot-video-annotation-2026-08-17.md` 两条 Important 是否关闭，以及修复后有无新的 Critical / Important。未改 overlay / 业务代码。工作区无 `label_studio/`、`web/`，diff 不含内核改动。

Reviewer 独立复跑（不是采信 Coder 自报）：

- `python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py` 退出码 0，10 项 PASS（single-view, multi-view, tasks, export-fixture, missing-video, empty-annotation, whole-only, partial-timeline, overlap, official-export-package）
- `python3 docs/harness/evals/test_robot_video_annotation.py` 9/9，`pass_rate=1.00`

上轮两条 Important 均关闭，见下。无新的 Critical / Important。硬阈值有本轮复跑与探测证据。

# Critical Issues

（无）

# Important Issues

（无）

上轮 Important 关闭证据：

1. **`check_export` 误套夹具规则** — 已关。`check_export` 已删除。`check_export_fixture()` 只验裸 `{result:[...]}` 夹具（四标签、两段 Static、整段字段、五段 start/end 写死）。`check_annotation_shape()` / `extract_results()` 验任意合法标注。Reviewer 复测上轮三条误杀用例：
   - 只有 `Static` + `grasp`：形状通过；夹具检查拒绝（`缺少标签 Place`）
   - 四标签 + 两段 Static、未填整段：形状通过；夹具检查拒绝（`必须同时含整段字段`）
   - 官方整包 `[{data, annotations:[{result:[...]}]}]`：形状通过；夹具检查拒绝（`不是官方 Export 整包`）
   合同边界复测：空 `result`、只有整段、相交、仅时间轴一段 Static，形状检查均通过。带官方多余字段（`id` / `completed_by` / `predictions`）的整包也能还原区间。

2. **README 导出对账按字面做不通** — 已关。现文写明：Export 选 **JSON**；官方导出是 task 数组，对账读 `annotations[].result`；不要把真实 Export 整包丢给 `check_overlay.py`；检查与种子均从仓库根用完整路径；浅克隆不要 `docker-compose up`（根目录 compose 含 `build: .`）；样例视频若 404 改成本地上传 / 可访问 URL。`seed_project.py` 把非 JSON 响应收成 `RuntimeError` → `ENV_FAIL`（退出码 2）。合同硬阈值已写清夹具 ≠ UI Export 整包。

# Test Gaps

- `extract_results()` 把任意 list 都当成官方 task 数组。把 README 所说的对账对象——裸 `annotations[].result`（result 条目列表）——直接交给 `check_annotation_shape()`，会静默得到 `[]`（空标注是合法路径，属于假通过）。官方整包与 `{result:[...]}` 两条合同路径是通的；缺的是「裸 result 列表必须失败或按 result 解析」的锁。CLI 不接收外部文件，用户按 README 手工对账不会踩到，故不升 Important。
- `test_run_all_pass_rate` 仍是再跑一遍 `run_all()`，并写死 `total = 10`。`pass_rate=1.00` 与检查脚本 10 项 PASS 仍有重叠；本轮独立性主要来自第二套时间轴 / 错误大小写 / 五段写死 / 形状边界这些新断言，不是来自这一项。
- 手册占位 `start` / `Movement` 混入起步模板：仍无负例。
- `timeline_segments` 仍只用 `timelinelabels[0]`；同一 item 多 range 会复用第一个标签名。现行为是接受并展开，eval 未锁这个假设。
- `seed_project.py` 的非 JSON → `ENV_FAIL` 只有代码路径，没有 eval。
- 缺 `video` 已断言错误原因；`{"video": ""}` 仍被拒，合同只写了缺字段。

# Contract Gaps

- Docker / API 冒烟按合同可只报环境；本机仍无发行版点过「贴模板 → 导入 → 标多段 → 提交 → 导出对账」。不构成本轮合同失败，规格成功标准里的真机路径仍未闭合。
- 合同用「官方 Export 整包（`annotations[].result`）」兼指整包与对账字段，容易让人以为裸 result 列表也是形状检查入口。实现只认 `{result:[...]}` 或 task 数组。

# Suggestions

- `extract_results`：list 项若没有 `annotations` / `data`，应明确拒绝，或识别为裸 result 列表再按条目校验。不要把未识别 list 收成空结果。
- eval 补一条：`check_annotation_shape([{from_name, to_name, type, value}])` 不得返回 `[]` 当成功。
- `test_run_all_pass_rate` 的 `total` 从 `run_all` 实际项数读取，避免写死。
- 有发行版时按 README 走一遍 UI 导出，确认 JSON 整包能用 `annotations[].result` 对上夹具五段。
