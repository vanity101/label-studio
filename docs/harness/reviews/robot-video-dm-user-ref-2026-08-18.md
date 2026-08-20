# Review Result

PASS

审查对象：Data Manager 任务表在 `annotators: [1]` 且 `AppStore.users` 无 id=1 时 MST `types.reference(User)` 整页崩溃。声称实现是 `setList` / `applyTaskSnapshot` 前 `ensureUserStubs`。未改业务代码。这不是采信 Coder 聊天。

线上：`runtime-eval@example.com`（whoami id=2）打开 `http://127.0.0.1:8080/projects/4/data`（随后被前端补成 `?tab=2`，**没有** `?task=`）。可见 **New Project #3**、**Tasks: 1 / 1**、行 ID **2**。`document.body` 无 `Failed to resolve reference`。

硬阈值均有本轮复跑与真机证据。Critical / Major 为空。

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
$ python3 docs/harness/evals/test_robot_video_ux_reorder.py
PASS test_move_before_first_row
PASS test_drop_on_body_is_before_not_nest
PASS test_click_span_ignores_display_order
PASS test_outliner_is_wired_for_flat_timeline_reorder
PASS test_multi_view_xml_was_not_rewritten
PASS test_previous_evals_still_hold
6/6 passed, pass_rate=1.00
EXIT:0
```

```
$ python3 docs/harness/evals/test_robot_video_dm_user_ref.py
PASS test_ensure_user_stubs_exists_on_app_store
PASS test_set_list_stubs_users_before_assigning_tasks
PASS test_bun_coverage_mentions_numeric_annotators
PASS test_multi_view_xml_was_not_rewritten
4/4 passed, pass_rate=1.00
EXIT:0
```

```
$ cd web && bun test --dom libs/datamanager/src/stores/Assignee.test.js libs/datamanager/src/stores/AppStore.test.js libs/datamanager/src/stores/DataStores/__tests__/tasks.test.js
bun test v1.3.14 (d1632b29)

libs/datamanager/src/stores/Assignee.test.js:
(pass) Assignee preProcessSnapshot (FIT-1658) > embeds flat profile fields from API payload
(pass) Assignee preProcessSnapshot (FIT-1658) > embeds nested user object when API provides user
(pass) Data Manager User reference stubs > treats bare numeric annotators as User references
(pass) Data Manager User reference stubs > does not throw when annotators are [1] and users is empty

libs/datamanager/src/stores/AppStore.test.js:
(pass) ... FIT-1949 / UTC-1043 共 11 项 ...
(pass) AppStore.ensureUserStubs > inserts empty User shells for missing ids and skips ones already present

libs/datamanager/src/stores/DataStores/__tests__/tasks.test.js:
(pass) ... 共 7 项 ...

Eenum_literal: Failed to create lcov file
EPERM: /Users/vanity/Public/label-studio/web/coverage/.lcov.info.*.tmp: Operation not permitted (open())
```

上述 bun 断言全部 `(pass)`。进程退出码 1 是只读沙箱写 coverage 被拒，不是测试失败。

# 源码核对（不是聊天）

`setList` 在 `self.list = [...newEntity]` / `self.list.push(...newEntity)` **之前**调用 stub：

```84:108:web/libs/datamanager/src/mixins/DataStore/DataStore.js
    setList({ list, total, reload, associatedList = [] }) {
      const root = getRoot(self);
      const records = [...(list ?? []), ...(associatedList ?? [])];
      root.ensureUserStubs?.(records.flatMap((item) => collectReferencedUserIds(item)));
      // ...
      if (reload) {
        self.list = [...newEntity];
      } else {
        self.list.push(...newEntity);
      }
```

`applyTaskSnapshot` 在 `updateItem` 前同样 stub。`collectReferencedUserIds` 对裸数字 `1` 会收集；对带 `email` 的完整 User 对象返回 `null`（bun：`{ user_id: 42, email: "sam@example.com" }` → `null`）。

`fetchUsers` 从 `self.users.push(...list)` 改成按 id 跳过已有项，避免 stub 后再 push 完整 User 触发 identifier 冲突。datamanager 源码里 **没有** `fetchUsers(` 调用点；任务表仍能靠 stub 活下来。

本轮 datamanager diff 7 个文件。`configs/multi-view.xml` 仍含「异常」「abnormal」。未把 Vite 入口改成 Webpack `main.js`。

# 线上（Playwright + API，不是 Coder 口述）

- 登录态：`runtime-eval@example.com`（id=2）。首页可见 New Project #3。
- 直接打开 `/projects/4/data` → `http://127.0.0.1:8080/projects/4/data?tab=2`（无 `task=`）。
- 可见：项目名、`Tasks: 1 / 1`、`Submitted annotations: 1`、表头 Annotated by、行 `2`。
- `hasMstError=false`。控制台无 User reference 错误（Sentry envelope 失败与一条 `TypeError: Illegal invocation` 与本合同无关）。
- 应用入口：`type="module"` `src=http://127.0.0.1:8080/react-app/main-Dp4X_ts7.js`。无 `runtime.js` / `vendor.js` / 经典 `/react-app/main.js`。
- manifest：`main.js` → `/react-app/main-Dp4X_ts7.js`（不是 Webpack `main.js`）。入口 + `src-*.js` blob 含 `ensureUserStubs`、`handleLabelClick`。
- 实际任务接口 `GET /api/tasks?page=1&page_size=30&view=2&project=4`：`"annotators":[1]`，`"updated_by":[{"user_id":1}]`。这就是会走 `types.reference(User)` 的形状。

docker.sock 在 Reviewer 只读沙箱被拒，未能 `docker inspect zhiyuan-ls`。8080 上的 Vite hash 包与 `ensureUserStubs` 字符串是独立证据。

# Critical Issues

（无）

# Major Issues

（无）

# Minor Issues

- 「Annotated by」列显示字面量 `1`，不是用户名。`fetchUsers` 未被调用；stub 空壳 `email=""`。合同验收的是不崩，不是芯片文案。
- `fetchUsers` 若以后被接上，对已 stub 的 id 会 `continue`，真资料进不来。要显示名字需要 patch 空壳，不能再 `push` 第二个 identifier。
- 控制台 `TypeError: Illegal invocation`（`main-Dp4X_ts7.js`）。任务表仍渲染。

# Test Gaps

- `docs/harness/evals/test_robot_video_dm_user_ref.py` 只 grep 源码，不打开 `/projects/4/data`。本轮 Playwright 补了这条。
- `tasks.test.js` 把 `collectReferencedUserIds` mock 成 `() => []`，`applyTaskSnapshot` 路径没有真实 stub 断言。空 users + `annotators: [1]` 的 MST 行为在 `Assignee.test.js`。

# Contract Gaps

（无。硬阈值均有独立证据。）

# Suggestions

- 下一轮若要显示标注员名字：在 stub 之后用 `fetchUsers` **更新**已有空壳，不要再 create 同 id。
- 把「打开 `/projects/4/data` 无 MST 红页」写进 Python/Playwright eval，避免只靠源码字符串。
