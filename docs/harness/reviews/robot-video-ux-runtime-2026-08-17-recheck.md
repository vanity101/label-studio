# Review Result

PASS

审查对象：方向 A（官方 HTML 改为 `type=module` 加载 Vite dist；Dockerfile 把 Vite dist + manifest 拷到官方镜像 `label_studio/core/static_build/js/manifest.json`），以及正在跑的 `zhiyuan-label-studio:ux`（容器 `zhiyuan-ls`，数据卷 `/Users/vanity/Public/mydata`）上标注员路径是否真的点标签切段。未改业务代码。未改原 FAIL 文件 `docs/harness/reviews/robot-video-ux-runtime-2026-08-17.md`。

这不是采信 Coder 聊天。Reviewer 独立复跑了合同检查、登录后 HTML、Dockerfile / 容器静态树、以及 Playwright 点 `Place`。

Reviewer 独立复跑（原样输出）：

```
$ python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py
PASS
checked: single-view, multi-view, tasks, export-fixture, missing-video, empty-annotation, whole-only, partial-timeline, overlap, official-export-package, discard-choices, discard-not-span
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_annotation.py
PASS test_single_view_has_one_timeline_and_required_labels
PASS test_multi_view_structure
PASS test_tasks_require_video_field
PASS test_export_fixture_restores_all_ranges
PASS test_annotation_shape_allows_empty_whole_partial_overlap_and_official_package
PASS test_granularity_is_not_a_second_timeline
PASS test_second_timeline_is_rejected
PASS test_wrong_label_case_is_rejected
PASS test_run_all_pass_rate
9/9 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_ux.py
PASS test_click_span_first_and_continue_and_overlap
PASS test_last_created_is_click_order_not_start_frame
PASS test_discard_blocks_new_spans
PASS test_single_view_discard_is_on_top_bar
PASS test_multi_view_xml_was_not_rewritten
PASS test_discard_export_is_choices_not_ranges
PASS test_editor_click_to_span_is_wired
PASS test_dockerfile_is_official_image_plus_frontend
PASS test_previous_overlay_eval_still_holds
PASS test_second_timeline_still_rejected
10/10 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_ux_runtime.py
PASS test_dockerfile_is_official_plus_frontend
PASS test_dockerfile_does_not_alias_vite_onto_webpack_main
PASS test_overlay_html_loads_vite_as_module
PASS test_live_homepage_is_not_blank
PASS test_live_app_js_is_vite_with_click_to_span
5/5 passed, pass_rate=1.00
EXIT:0
```

```
$ cd web && bun test --dom libs/editor/src/tags/control/__tests__/timelineClickToSpan.test.js
bun test v1.3.14
(pass) nextClickSpan > first label uses frame 1 through playhead
(pass) nextClickSpan > later label continues from previous end + 1 when playhead is later
(pass) nextClickSpan > allows overlap when playhead is at or before previous end
(pass) nextClickSpan > treats invalid playhead as frame 1
(pass) lastCreatedTimelineRegion > picks the last created timeline region by ouid, not start frame
(pass) lastCreatedTimelineRegion > ignores non-timeline regions
(pass) resolveNamedTag > finds a tag when Map keys are name@annotationId
(pass) resolveNamedTag > falls back to objects when names.get misses
(pass) discard helpers > recognizes 废弃 as a whole-video mark, not a span label
(pass) discard helpers > filters 废弃 out of phase label dropdown options
(pass) applyPhaseLabel > switches the label via the control and does not run when discarded
```

11 项测试均 pass。只读沙箱写 `web/coverage/.lcov.info.*.tmp` 报 EPERM，进程退出码 1。这是覆盖率落盘被拒，不是断言失败。

容器（docker inspect / exec，不是 Coder 口述）：

- `zhiyuan-ls` image=`zhiyuan-label-studio:ux`，Up，`0.0.0.0:8080->8080/tcp`
- 数据卷 `/Users/vanity/Public/mydata -> /label-studio/data`
- 容器内 `base.html` 第 209 行：`<script type="module" ... src="{% manifest_asset 'main.js' %}">`
- `core/static_build/js/manifest.json`：`{"main.js":"/react-app/main-D61Yq3tX.js", ...}`
- Dockerfile runtime stage：`FROM heartexlabs/label-studio:latest`；没有 `cp ... main-*.js ... main.js`
- `/react-app/main.js` **仍是官方 Webpack**（`webpackChunk`，2026-03-11 层）。HTML **没有**把它当应用入口。这是「没覆盖 Webpack main.js」，符合禁止项。

登录后 HTML（Playwright，账号已是 `runtime-eval@example.com`，不是未登录登录页）：

- URL `http://127.0.0.1:8080/`，标题 `Home | Label Studio`
- `.app-wrapper` 存在且有子节点；可见 Welcome / `New Project #3`
- 应用脚本：`type="module"`，`src="http://127.0.0.1:8080/react-app/main-D61Yq3tX.js"`
- 没有 `runtime.js` + `vendor.js` + 经典 `/react-app/main.js` 作为应用入口
- 未登录首页走 `user_base`，不含 `type=module` / `app-wrapper`。合同硬门槛的「不是白屏」对该页也成立（有 Label Studio / Log in）。应用入口断言必须打登录后页；本轮打了。

侍出 JS 字符串（manifest 入口 + 两个 `src-*.js` chunk）：

- `handleLabelClick`：在 blob 中，2 处
- `TimelineLabelsClickToSpan`：在 blob 中，1 处
- `nextClickSpan`：生产 minify 后字面量不在包里（源码 `timelineClickToSpan.js` 仍导出该函数；eval 允许 `nextClickSpan or TimelineLabelsClickToSpan`）
- 官方 Webpack `/react-app/main.js` 不含上述切段字符串

Playwright 点 `Place`（`New Project #3` id=4，任务 2，顶部有「废弃」）：

- 打开时已有未提交区间 Place `start=1 end=42`（Coder 留下的草稿）。Reset 按钮 disabled（无 undo 历史）。页面上也没有「Create an annotation」按钮。
- Reviewer 经 `annotationStore.createAnnotation()` + `selectAnnotation('DjaUv')` 得到空 Regions（0 段），再 `video.setFrame(30)` 等到 `currentFrame===30`，点击顶部 `Place`。
- 结果：1 段 `timelineregion`，`labels=["Place"]`，`ranges=[{start:1,end:30}]`；`Place.selected===false`。侧栏 `treeitem "1 Place"`。
- **不是**官方单帧（`start=end=30` 且 Place 保持选中）。

`configs/multi-view.xml` 仍含「异常」「abnormal」；UX eval `test_multi_view_xml_was_not_rewritten` 绿。

硬阈值有本轮复跑与真机点标签证据。无 Critical / Important。

# Critical Issues

（无）

# Important Issues

（无）

重点怀疑项的结论：

1. **不是白屏。** 未登录页有登录界面；登录后有 `app-wrapper`、Welcome、项目列表。应用入口是 Vite hash module，不是空 document。
2. **入口不是 Webpack `main.js`。** 登录后唯一应用脚本是 `type=module` 的 `/react-app/main-D61Yq3tX.js`。Webpack 三文件仍可被直接请求到，但 HTML 不再把它们当应用入口。Dockerfile runtime stage 没有把 Vite 文件 `cp` 成 `main.js`。
3. **切段逻辑在实际加载的包里。** `handleLabelClick` 与 MST 模型名 `TimelineLabelsClickToSpan` 在 Vite chunk 中。官方 Webpack `main.js` 没有这些字符串。
4. **点 Place 切段已进标注员路径。** 播放头 30，点 Place → start=1 end=30，Place 不保持选中。与上一轮 FAIL（区间 132–132、Place 保持选中、HTML 仍 Webpack）相反。
5. **未改多视角 XML。** `configs/multi-view.xml` 仍有「异常」「abnormal」；叠加 eval 绿。
6. **叠加合同仍绿。** overlay / annotation / UX Python eval 本轮独立复跑全绿。
7. **`nextClickSpan` 字面量被 minify 掉。** 不升 Critical：行为已用 Playwright 锁住；eval 合同写的是 `nextClickSpan or TimelineLabelsClickToSpan`。见 Contract Gaps。

# Test Gaps

- `test_robot_video_ux_runtime.py` 不打开浏览器、不登录、不点 `Place`、不读 Regions 的 start/end。`test_live_homepage_is_not_blank` 只 curl 未登录页（该页走 `user_base`，本来就不加载 app JS）。`test_live_app_js_is_vite_with_click_to_span` 只对 manifest + JS 做字符串检查。本轮 Playwright 是 Reviewer 手跑，没有写进 eval，下次 Coder 自报 PASS 时仍可能只绿 Python。
- Dockerfile 断言用正则 `cp ... main-*.js ... main.js`，挡不住 `COPY` / `mv` / 无通配符的单文件覆盖。本轮容器里 Webpack `main.js` 仍在，HTML 不引用它，所以没踩中。
- bun 单测覆盖公式与 discard helper，没有 MST 集成：不创建 TimelineLabels、不点 Label、不检查 Regions。
- 本轮用 `createAnnotation()` 清草稿，因为 Reset disabled。eval 没有「存在未提交草稿时仍能切段」的路径。

# Contract Gaps

- 合同 Hard thresholds 写「侍出 JS 含 `handleLabelClick` 与 `nextClickSpan`」；Vite 生产包会吃掉 `nextClickSpan` 这个本地导出函数名，只留下 `handleLabelClick`（MST action）和 `TimelineLabelsClickToSpan`（model 名）。eval 已放宽为二者之一。字面合同与 eval / 生产 minify 不一致。行为已验证，故不因此 FAIL。
- runtime eval 没有 Playwright 切段步骤，而规格 Success Criteria 和 Verification 都要求独立点 `Place`。本轮由 Reviewer 补上；合同文件本身仍把 UI 核验写在 Python eval 之外。
- 「Reset / Create an annotation」在已有 userGenerate 草稿时并不出现可用按钮。核验步骤应写清：Reset disabled 时允许新建空 annotation 再点标签。

# Suggestions

- 把 Playwright（或等价无头）点 `Place` → start=1 end=N、`selected===false` 写进 `test_robot_video_ux_runtime.py` 或单独脚本，避免下一轮只绿 curl。
- 若仍要用字符串锁切段，在 `timelineClickToSpan.js` 留一个不会被 minify 掉的标识（例如已有的 `TimelineLabelsClickToSpan`），并改合同 Hard thresholds 与 eval 一致。
- 登录后 HTML 断言不要写进只 curl `/` 的测试；对 `user_base` 与 `base.html` 分流写明。
- 原 FAIL 文件保留作事故记录。本文件只证明侍出入口已闭合，不假装上一轮没发生。
