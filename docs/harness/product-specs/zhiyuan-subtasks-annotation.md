# 智源：子任务标注与导出（已拍板）

本文是标注合同，给实现 / multica agent 用。和 `zhiyuan-lerobot-import.md`（导入播视频）分开：本文件只定 **怎么标、怎么校、Export 吐什么**。

人只确认验收，不代替 Verify。改模板、切段校验或 Export 后：Playwright MCP 登录后的应用页上，必须真实点击新增/改动的控件（含 Place、质量轴、提交拦截、Export），并留下截图或等价证据；跑 `python3 docs/harness/evals/test_robot_video_ux_runtime.py`。curl / 源码 grep 不算完成。

---

## 一句话

有效动作 = 时间轴上打的子任务标签。人做两件事：第一条轴铺满子任务，第二条轴只标异常帧。点 Export 直接下载合同 JSON（不是官方 `result`，也不另写 sidecar）。

---

## 标签（第一条时间轴）

五种，字面量必须一致：

| `name` | 含义 |
| --- | --- |
| `Static` | 从第 0 帧到开始干活之前的静止 |
| `reach_object` | 伸手 / 靠近 |
| `grasp_object` | 抓住 |
| `place_object` | 放下 |
| `End` | 最后一个动作做完之后到片尾的静止 |

- **有效动作就是这些标签**，没有单独的「有效动作」字段或控件。
- `Static` / `End` 也是子任务，计入铺满。片头没有静止就不必强行有 `Static`；片尾没有收势就不必强行有 `End`。有空档则必须用标签填上（含这两段）。
- 同一 `name` 可以出现多次，**不固定顺序**（例如再来一轮 reach → grasp → place）。
- 从现有模板改掉：`grasp` → `grasp_object`，`Place` → `place_object`，并增加 `reach_object`。
- 点标签切段的交互保留（第一段从播放头往回接到上一段结束的下一帧）。但不再允许重叠。

---

## 铺满规则

非废弃任务：

- 每一帧恰好属于一个子任务。
- **禁止重叠，禁止留空。**
- 帧号 **0 起、闭区间**。第一段必须 `start_frame=0`，最后一段必须 `end_frame=T-1`。相邻段 `end_frame + 1 == 下一段 start_frame`。
- 标注页仍是 Label Studio 的 1 起；**写出 JSON 时减 1**。

废弃任务：**免检**（不要求铺满、不查重叠），且 **不进入** 本合同 Export。

---

## 提交

- 废弃：可提交，不做铺满/重叠检查。
- 非废弃：未铺满或出现重叠 → **告警，且不可提交**。
- 质量轴未画视为全 1，不挡提交。

---

## 帧级属性（第二条时间轴）

后续会有多种帧级属性；现在只做 **行为质量** `action_quality`。

- 界面：**第二条时间轴**画质量=0 的段。
- 默认：每一帧 `action_quality=1`（正常）。
- 审查发现冗余或错误：在第二条轴上画出对应区间，这些帧为 `0`。
- `0` 段 **可以跨过子任务边界**（与第一条轴独立）。
- 未画到的帧保持 `1`。
- 导出时必须 **每一帧都有** 属性对象，key 覆盖 `0 … T-1`，一个不漏。

模板里拿掉：

- 「信息复杂度」`granularity`（简单 / 中等 / 复杂）
- 「动作序列」`action_sequence` 文本框

整集「废弃」保留。

---

## Export JSON

点 **Export** 直接吐下面这种 JSON。不要官方 LS `result`（`ranges` + `timelinelabels`），不要每集 sidecar。

多任务是 **数组**，用 `episode_id` 对齐：

```json
[
  {
    "episode_id": "episode_000000",
    "subtasks": [
      {"name": "Static", "start_frame": 0, "end_frame": 2},
      {"name": "reach_object", "start_frame": 3, "end_frame": 5},
      {"name": "grasp_object", "start_frame": 6, "end_frame": 8},
      {"name": "place_object", "start_frame": 9, "end_frame": 11},
      {"name": "End", "start_frame": 12, "end_frame": 14}
    ],
    "frame_attributes": {
      "0":  {"action_quality": 1},
      "1":  {"action_quality": 1},
      "2":  {"action_quality": 1},
      "3":  {"action_quality": 1},
      "4":  {"action_quality": 1},
      "5":  {"action_quality": 0},
      "6":  {"action_quality": 0},
      "7":  {"action_quality": 1},
      "8":  {"action_quality": 1},
      "9":  {"action_quality": 1},
      "10": {"action_quality": 1},
      "11": {"action_quality": 1},
      "12": {"action_quality": 1},
      "13": {"action_quality": 1},
      "14": {"action_quality": 1}
    }
  }
]
```

上例 T=15，帧 `0…14`。第 5、6 帧质量为 0（跨过 reach→grasp）。`frame_attributes` 的 key 在 JSON 里是字符串 `"0"`…`"14"`。

| 字段 | 规则 |
| --- | --- |
| `episode_id` | 与任务 `data.episode_id` 一致 |
| `subtasks` | 第一条轴；`name` + `start_frame` + `end_frame`（0 起闭区间） |
| `frame_attributes` | 字典，**key=帧号**；每帧一个对象；现在必有 `action_quality` ∈ {0,1} |
| 以后加帧属性 | 写进同一帧对象，例如 `{"action_quality": 1, "其他": ...}`，不必改 `subtasks` |

废弃任务不出现在数组里。

---

## 转回 LeRobot（后续，本轮可不做）

- `action_quality` 以及之后新增的帧级字段：写入该集 **parquet 列**（一行一帧，与 `frame_index` 0 起对齐）。**不要写进 yaml。**
- `subtasks` 是整段切分，留在 episode 级 meta（json / jsonl），不进 parquet。
- Label Studio 点 Export 仍然先出上面的 JSON；转包是另一步。

---

## 相对现状要改什么

现模板 `docs/harness/overlays/zhiyuan-robot-video/configs/single-view.xml`：

- 标签：`Static` / `grasp` / `Place` / `End`
- 切段允许重叠（播放头早于上一段结束时）
- 有细致度、动作序列
- Export 是官方 LS 包

本需求要求改为五标签、禁止重叠留空、第二条质量轴、提交拦截、Export 合同 JSON。

导入（HDF5 一集最小包、LeRobot 尚未接）见 `zhiyuan-lerobot-import.md`，本文件不改导入。

---

## 明确不做

- 单独的「有效动作」起止控件或导出字段
- 把 `frame_attributes` 整份字典塞进 yaml
- 强制每集都有 `Static` 和 `End`
- 固定 reach → grasp → place 顺序
- 用整集「废弃」代替 `action_quality=0`
- 本轮实现 LeRobot 回写 parquet（只定数据落点）

---

## 验收要点

- 非废弃：缺一帧或两段重叠 → 有可见告警，Submit 点了无新 annotation。
- 废弃：可不铺满，能提交；Export 数组里没有该 `episode_id`。
- 质量轴默认全 1；画一段 0 后，导出对应 key 为 0，可跨子任务。
- Export 根是数组；`frame_attributes` 的 key 集合等于 `{0,1,…,T-1}`。
- 模板没有细致度 / 动作序列；有 `reach_object` / `grasp_object` / `place_object` / `Static` / `End` / 废弃。
