# Contract: Data Manager 缺失 User 引用

本轮只修 Data Manager 任务表因 MST 无法解析 `annotators` 里的 User id 而整页崩溃。叠加在已有 overlay / UX / runtime 之上，不改切段公式、不改多视角 XML、不把 Vite 覆盖成 Webpack `main.js`。

## Deliverables

- 任务列表在创建 `annotators` / `reviewers` 等 User 引用之前，把缺失的用户 id 补进 `users` 空壳
- 打开 `/projects/4` 或 `/projects/4/data`（不必带 `?task=`）不再因 `Failed to resolve reference '1' to type 'User'` 整页红错
- 对应 bun 单测；上一轮 Python eval 仍绿

## Verification

- `cd web && bun test --dom libs/datamanager/src/stores/Assignee.test.js`
- `python3 docs/harness/evals/test_robot_video_ux.py`
- `python3 docs/harness/evals/test_robot_video_ux_runtime.py`（镜像重建并启动后）
- 打开 `http://localhost:8080/projects/4` 或 `/projects/4/data` 可见任务表，不是 MST User 引用错误页

## Hard thresholds

- bun 单测：空 `users` 时用 `annotators: [1]` 创建任务列表不得抛 MST reference 错误
- 源码：`ensureUserStubs` 存在，且任务 `setList` 前会调用
- 不改 `configs/multi-view.xml`；不改 ouid / 切段公式

## Failure behavior

- 无法补齐引用时返回明确错误，禁止把「请用带 task= 的 URL」当修复
- 禁止完整 clone、禁止重写核心
