# Review Result

PASS

审查对象：`docs/harness/exec-plans/active/label-studio-annotation-ux.md` 声称完成的前端交互（简单单视角），叠加在上一轮 overlay 之上。未改业务代码或 overlay 实现。

Reviewer 独立复跑（不是采信 Coder 自报）：

- `python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py` 退出码 0，12 项 PASS（single-view, multi-view, tasks, export-fixture, missing-video, empty-annotation, whole-only, partial-timeline, overlap, official-export-package, discard-choices, discard-not-span）
- `python3 docs/harness/evals/test_robot_video_annotation.py` 9/9，`pass_rate=1.00`
- `python3 docs/harness/evals/test_robot_video_ux.py` 10/10，`pass_rate=1.00`
- 本机 Python 3.9.6；无 bun；有 docker 二进制，未执行 `docker build`（合同写明 ENV 不判失败）
- 源码对照（不是 grep 测试）：切段接到 `Label.onClick` / `onLabelInteract`；废弃锁在 `addTimelineRegion` / `startDrawing` / `setRange` / `isReadOnly` / 侧栏；`RegionStore.js` 与 `configs/multi-view.xml` 无 diff；未改 `Timeline/` 播放器内核

硬阈值有本轮复跑与源码对照证据。无 Critical / Important。

评审落盘后 Coder 补了一行：`HtxVideo.jsx` 的 Timeline `readonly` 并上 `item.isDiscarded`（对应下方 Suggestions，不改变 PASS 结论）。

# Critical Issues

（无）

# Important Issues

（无）

重点怀疑项的结论：

1. **点标签切段接到了 Label 点击，不是只有纯函数。** `Label.jsx` 的 `onClick` / `onHotKey` → `onLabelInteract` → 若 parent 是 `timelinelabels` 则调用 `handleLabelClick`。`TimelineLabels.js` 的 `handleLabelClick` 按 `nextClickSpan` 计算后 `addTimelineRegion` + `setRange`。仅当 annotation 里存在 `Choices name="discard"` 时启用，其它 TimelineLabels 项目仍走官方「先选再画」。
2. **废弃不只是挪 XML。** 点废弃后：`handleLabelClick` 直接 return true（不再切段、也不落到 `toggleSelected` 改名）；`Video.addTimelineRegion` / `startDrawing` 直接 return；`TimelineRegion.setRange` 与覆盖后的 `isReadOnly()` 锁改帧；侧栏下拉 `disabled`、起止帧 `onChange` 被拿掉。已有区间仍在 `regionStore`。Annotation 本身未变只读，Submit 不被这块锁住。
3. **废弃不会做成 `timelinelabels` ranges。** 单视角模板里「废弃」是 `Choices name="discard"`，且检查禁止把它放进 `TimelineLabels` 的 Label。`handleLabelClick` 对 `label.value === "废弃"` 直接 false。`activeStates()` 只收 `*labels`，Choices 不会作为 additionalStates 写进时间轴结果。
4. **Regions「先点的在上」沿用官方 `sort=date` / `ouid` 升序，没有被改成默认 `mediaStartTime`。** `RegionStore.js` 本轮零 diff。新会话默认 `date`+`asc` = 创建顺序、先点的在上。`mediaStartTime` 仍是可选项，只在用户选了或 `localStorage outliner:sort` 已是该值时才会按开始帧排。
5. **测试确实偏静态。** 见 Test Gaps。实现不是 stub；公式 Python/JS 对照一致。
6. **未改多视角 XML。** `configs/multi-view.xml` 无 diff；文件仍含「异常」「abnormal」。eval 对此有负例锁。
7. **未重写播放器 / 时间轴内核。** `web/libs/editor/src/components/Timeline/` 无作为重写的 diff。`Video.js` 只加了 `isDiscarded` 与两处守卫。

# Test Gaps

- `test_editor_click_to_span_is_wired` 只 grep 源码字符串。空函数或注释里出现这些字符串也会过。`RegionStore` 那两处本轮根本没改，grep 的是上游原样。
- Python `click_span.py` 与 JS `timelineClickToSpan.js` 是两份手写公式。eval 只跑 Python 侧。本轮对照过公式一致；没有自动化锁两份不漂移。
- `test_discard_blocks_new_spans` 只断言 `can_create_span(True) is False`，不跑 `addTimelineRegion` / `startDrawing` / `setRange` / 侧栏 `locked`。
- `test_discard_export_is_choices_not_ranges` 用手工拼的 `{result:[...]}`，不是编辑器 serialize，也不是 UI Export。夹具 `annotation-export.json` 仍不含 discard 条目。
- 存在 `timelineClickToSpan.test.js`，但本机无 bun，未跑。即便跑了，也没有 MST 集成：不创建 TimelineLabels 模型、不点 Label、不检查 Regions 列表顺序。
- 无测试覆盖：播放头非法 / `addTimelineRegion` 返回 undefined 时 `handleLabelClick` 仍 return true（点击被吞）；废弃后时间轴看起来仍可拖（评审后已把 `HtxVideo` readonly 并上 `isDiscarded`）。
- `test_run_all_pass_rate` 仍写死 `total = 12`，且先 `assert not errors`。与 `check_overlay.run_all()` 重叠，不提供独立前端证据。

# Contract Gaps

- 合同 Verification 接受 Python eval + overlay 检查作为硬门槛，不要求 Cypress / 真机点标签。规格 Success Criteria 里的「点标签 → Regions 出现段 / 点废弃 → 不能再改」没有 UI 证据。源码对照认为路径是通的，但标注员真机路径仍未闭合。
- 自建镜像：Dockerfile 存在且 `FROM heartexlabs/label-studio:latest`，满足合同字面。它把 builder 的整个 `web/` 和 `label_studio/core/static/js` 拷进发行版镜像，没有像根目录 Dockerfile 那样拷 `web/dist` 并 `collectstatic`。发行版实际侍出的静态文件是否被替换，本轮未 build，不能当作已验证。合同把 docker build 标成 ENV，故不升 Important。
- `AGENTS.md` 写 Python 3.10+；本机 3.9.6。因 `from __future__ import annotations`，eval 仍能跑。不是产品缺陷。
- 合同「无法完成时返回明确错误」：切段失败时 `handleLabelClick` 多半静默 return true。overlay 场景下 `timelineControl` 存在，实际很难踩到。

# Suggestions

- 补一条不依赖 bun 也可选的 MST/纯 mock 测试：有 `discard` Choices 时点阶段 Label 必须调用 `addTimelineRegion` 且 `setRange([start,end])`；无 `discard` 时必须落到 `toggleSelected`。不要再用 grep 当「已接线」。
- 废弃锁补行为断言：`isDiscarded=true` 时 `addTimelineRegion` / `startDrawing` / `setRange` / `applyPhaseLabel` 为 no-op；侧栏 Label select `disabled`。
- 若验收机之前用过「By Media Start Time」，先清 `localStorage['outliner:sort']` 再看列表。本轮故意不改 RegionStore；要强制点击顺序需另开需求。
- overlay Dockerfile 应对齐根目录生产路径：只覆盖 `web/dist`（以及 collectstatic 产物），不要把含 `node_modules` 的整棵 `web/` 打进发行版。有 bun / 构建机时实建一次。
- `TimelineLabels.jsx` 现已是对 `.js` 的 re-export；可删掉死 `.jsx`，避免双文件。
