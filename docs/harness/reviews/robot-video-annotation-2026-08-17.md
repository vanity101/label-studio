# Review Result

NEEDS_CHANGES

审查对象：`docs/harness/overlays/zhiyuan-robot-video/` 与合同 `docs/harness/evals/robot-video-annotation.md`。未改业务代码。硬阈值已由 Reviewer 复跑：`check_overlay.py` 退出码 0（7 项 PASS）；`test_robot_video_annotation.py` 8/8，`pass_rate=1.00`。工作区无 `label_studio/`、`web/`，diff 不含内核改动。

# Critical Issues

（无）

# Important Issues

1. **`check_export` 把「完整夹具」规则误套到任意带时间轴的 result。**
   合同硬阈值只要求**导出夹具**能还原每段 `ranges.start` / `ranges.end`、含四字面量与两段 `Static`。合同边界同时写死：空 `result` 允许、只有整段允许、相交允许。实现却在 `check_export` 里一旦发现任意 `timelinelabels` 段，就强制四标签 + 两段 Static + 必须有整段字段。
   同一函数又被 `check_empty_annotation_allowed` / `check_whole_only_allowed` 当作通用标注策略入口，职责已经不是「只验夹具」。
   Reviewer 探测（均应视为合法标注或合法官方导出，却被拒绝）：
   - 只有 `Static` + `grasp`（简单细致度少标几段）→ `导出夹具缺少标签 Place`
   - 四标签 + 两段 Static、未填整段 → `完整导出夹具必须能区分整段字段与时间轴结果`
   - 官方整包 `[{data, annotations:[{result:[...]}]}]` → `导出夹具必须是含 result 的对象`
   这不是手册质检引擎，但已经在检查脚本里编造了「有区间就必须四标签齐全」的规则。手册原文是细致度越高标签越多，简单档本来就可以少标。必须拆成：夹具完整性检查 vs 标注形状检查（官方 `ranges` + `timelinelabels`，允许空 / 仅整段 / 部分区间 / 仅时间轴）。

2. **README 的「导出对账」按字面做不通。**
   成功标准要求启动说明能复现「贴模板 → 导入 → 标多段 → 提交 → 导出对账」。现状缺口：
   - 未写 UI 上点 Export、必须选 **JSON**（选 CSV / COCO 会对不上 `ranges`）。
   - 未写官方导出是 **task 数组**，对账对象是 `annotations[].result`，不是夹具那种裸 `{ "result": [...] }`。
   - 「导出」下一节直接放 `check_overlay.py`，未声明该脚本只验仓库夹具；把真实 Export 文件丢进去会失败（见上条探测）。
   - 可选种子写成 `python seed_project.py`，与上文从仓库根运行的检查命令不一致，根目录会找不到文件。
   Docker 启动命令本身（`docker pull` + `docker run` 官方镜像、不要源码构建）方向正确；缺的是导出对账闭环，不是拉镜像。

# Test Gaps

- 空标注 / 缺 `video` / 只有整段：有测，且 Reviewer 复跑通过。缺 `video` 的负例只断言「抛了 `CheckError`」，不断言错误原因；`{"video": ""}` 也被拒，合同只写了缺字段。
- 相交区间：合同写允许，实现未拒绝（探测 `overlapping-with-whole` 通过），但 eval **没有**对应用例。
- 部分时间轴、仅时间轴无整段、官方整包导出：无正向用例；当前 `check_export` 会误杀（见 Important 1）。
- `test_export_restores_ranges_and_two_statics` 只钉死第一段 `Static 1–20` 和末段是 `Static`，未断言 `grasp 21–40` / `Place 41–70` / `End 71–90`。
- 无负例：第二套 `TimelineLabels`、`static`/`end` 错误大小写、手册占位 `start`/`Movement` 混入起步模板。
- eval 8 项里有 5 项只是调用 `check_overlay` 且不抛异常；`test_run_all_pass_rate` 再跑一遍 `run_all()` 并写死 `total = 7`。`pass_rate=1.00` 与检查脚本 7 项 PASS **不是两份独立证据**。
- `timeline_segments` 只读 `ranges[0]` 与 `timelinelabels[0]`。官方文档写 one range per region，夹具也是一段一条；若同一 item 里写两段 Static，检查会当成只有一段（探测 `multi-range-one-item` 被拒）。无测试锁这个假设。

# Contract Gaps

- 硬阈值「夹具含两段 Static + 四标签」被实现扩成「任何带区间的 result 都必须」。合同没有把「任意合法标注必须四标签」写死；手册还要求简单档标签更少。
- 合同写「官方形状导出夹具」，夹具只覆盖 `result[]` 条目的 `ranges` + `timelinelabels`，未写清「不是 Label Studio Export 整包」。README 却按「导出后检查」来写。
- 相交允许已写进合同，未进入 eval。
- Docker / API 冒烟按合同可只报环境；本机 Docker 不可用，**「初步能跑」的 UI 路径仍无发行版证据**。这不构成本轮合同失败，但是规格成功标准里「能跟着做」尚未被真机点过。

# Suggestions

- 拆函数：`check_export_fixture()` 只验 `examples/annotation-export.json`；`check_annotation_shape()` 只验官方字段并落实合同四条边界。eval 对两种 payload 分别断言。
- README 补三句：Export 选 JSON；对账读 `annotations[].result`；不要对真实导出跑 `check_overlay.py`。种子命令写成 `python3 docs/harness/overlays/zhiyuan-robot-video/seed_project.py`。可加一句：浅克隆不要 `docker-compose up`（根目录 compose 含 `build: .`）。
- eval 增加：第二套时间轴必须失败；`static`/`end` 大小写必须失败；部分区间与仅时间轴必须通过形状检查。中间段 start/end 写死断言。
- `seed_project.py` 把非 JSON 响应收成 `ENV_FAIL`，避免 `JSONDecodeError` 冒成未分类崩溃。
- 样例视频 `/static/samples/opossum_snow.mp4` 未在本机镜像上证实仍存在；说明里写「若 404 就改成本地上传 / 可访问 URL」。
