# Review Result

PASS

审查对象：`docs/harness/exec-plans/active/label-studio-annotation-ux-reorder.md` 声称完成的右侧 Regions 扁平拖排序（独立 `outlinerOrder`，不改 ouid / 切段公式），叠加在 overlay / UX / runtime 之上。未改业务代码。

这不是采信 Coder 聊天。Reviewer 独立复跑了合同检查、源码 diff、线上 Vite 包字符串、以及 Playwright 三种落点实拖 + 拖乱后切段。

Reviewer 独立复跑（原样输出）：

```
$ python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py
PASS
checked: single-view, multi-view, tasks, export-fixture, missing-video, empty-annotation, whole-only, partial-timeline, overlap, official-export-package, discard-choices, discard-not-span
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_annotation.py
9/9 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_ux.py
10/10 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_ux_runtime.py
5/5 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_ux_reorder.py
6/6 passed, pass_rate=1.00
EXIT:0
```

```
$ cd web && bun test --dom libs/editor/src/components/SidePanels/OutlinerPanel/__tests__/flatReorder.test.js
(pass) moveId > inserts drag before drop, including the first row
(pass) moveId > inserts drag after drop
(pass) dropPlace > treats drop-on-body as insert-before, never nest
(pass) dropPlace > treats gap above first row as insert-before
(pass) dropPlace > treats gap below a row as insert-after
(pass) shouldFlatReorder > only flattens timeline regions
```

6 项断言均 pass。只读沙箱写 `web/coverage/.lcov.info.*.tmp` 报 EPERM，进程退出码 1。这是覆盖率落盘被拒，不是断言失败。

线上侍出：

- manifest `main.js` → `/react-app/main-6kYi0VWw.js`（不是 Webpack 文件名 `main.js`）
- 入口前 120 字节无 `webpackChunk`
- Vite blob 含 `applyFlatOutlinerOrder`、`outlinerOrder`
- Dockerfile runtime stage：`FROM heartexlabs/label-studio:latest`；没有 `cp ... main-*.js ... main.js`

源码对照：

- `OutlinerTree.tsx`：`timelineregion` 走 `applyFlatOutlinerOrder` 后 return；官方 `setParentID` 嵌套路径仍留给非时间轴
- `RegionStore.js`：新增 `outlinerOrder`；`sortedRegions` 在 order 非空时按它排；`asTree` 对 `type === "timelineregion"` 不挂 parent.children；没有写 `ouid`
- `configs/multi-view.xml` 本轮无业务改动

Playwright（`New Project #3` id=4，任务 2；`createAnnotation()` 空 Regions）：

- 未拖时名单 `Static, grasp, Place`
- 拖 Place 到 grasp 顶边 → `Static, Place, grasp`；帧不变；ouid 不变
- 拖 grasp 到 Static 顶边 → `1 grasp` 成为第一行；全部无缩进子节点
- 拖 grasp 到 Place 行中 → 并列换位，无 children
- 拖乱后 `setFrame(50)` 点 End → **start=31 end=50**（按创建最后一条 Place end=30），不是名单最后一行 grasp 的 21–50

硬阈值有本轮复跑与页面实拖证据。无 Critical / Important。

# Critical Issues

（无）

# Important Issues

（无）

# Test Gaps

- wiring 测试只 grep 源码字符串
- Playwright 三种落点未写进 Python eval
- bun 单测只覆盖纯函数，没有 MST / rc-tree `onDrop`

# Contract Gaps

- 合同 Verification 把 Playwright 写在 Python eval 之外，`pass_rate` 只统计 6 条 Python
- 当次页面顺序即可；刷新后是否还在，规格写明未确认

# Suggestions

- 把三种落点 + 拖乱后点标签收进 eval
- wiring 不要只 grep：mock 调 `applyFlatOutlinerOrder` 后断言顺序变、ouid/ranges 不变、asTree 无 children
