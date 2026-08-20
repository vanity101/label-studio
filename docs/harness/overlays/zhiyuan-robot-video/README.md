# 智源机器人视频标注（单视角 + 前端交互）



预置阶段标签（保持手册大小写）：`Static` / `grasp` / `Place` / `End`。

- `Static`：第一帧到机械臂未触动之前；以及收回不动之后到最后一帧
- `grasp`：完全抓住物品、未抬起之前
- `Place`：放下物品，爪夹完全松开
- `End`：最后一个动作做完，收到不动状态

点顶部阶段标签即切段：第一段 start=1、end=播放头；其后 start=上一标签结束帧+1、end=播放头。播放头早于上一结束帧时允许重叠（start=播放头、end=上一结束帧）。不必再在时间轴上画。

「废弃」与阶段标签同一条顶部栏。点击表示当前视频不可用：不能再标阶段、不能再改已有区间；已有区间仍可见；仍可提交。废弃导出为整段 `choices`（`from_name=discard`），不是时间轴 `ranges`。

## 启动（默认本机 :8081）

不要 `docker-compose up`（根目录 compose 含 `build: .`）。一键启动并打开网页：

```bash
python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py
```

默认走仓库 `.venv`，等 `http://127.0.0.1:8081/` 就绪后打开浏览器（账号 `rlds-verify@localhost` / `rldsverify123`）。脚本会注入 `DATA_UPLOAD_MAX_MEMORY_SIZE=1GB`、`NO_GCE_CHECK=true`、`RLDS_IMPORT_MAX_EPISODES=16`。本机 8081 已经能解 RLDS。旧的 8080 容器没有内嵌 TF，必须 `--docker --build --recreate` 之后才能在 8080 解码。

可选 Docker（容器内仍听 8080，主机 `--port`；重建后镜像内嵌 Debian Python+TensorFlow，**8080 也能解 RLDS**）：

```bash
python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py --docker --build --recreate --port 8080
```

点标签切段、侧栏改名、废弃锁定依赖这套前端。镜像把官方 HTML 改成 `type=module` 加载 Vite dist（见 `patches/base.html`），不要把 Vite 文件改名为 Webpack 的 `main.js`。只用 `heartexlabs/label-studio:latest` 时，模板仍能导入，但点击行为仍是官方「先选标签再画时间轴」。

## 建项目并贴模板

1. Create Project，名称自定。
2. Labeling Setup → Code，粘贴 `configs/single-view.xml` 全文，Save。
3. 按本任务动作需要更多描述时：切到 Visual，在标签栏 Add。不要改四个阶段字面量的大小写。
4. 帧率按模型组改 `frameRate`：10 / 15 / 25 / 30。必须与视频恒定帧率一致。建议 MP4 + H.264。**RLDS / TFRecord 导入的预览是 10fps**：贴 `configs/single-view-rlds.xml`，或把现有配置的 `frameRate` 改成 `10.0`。本轮不会自动改已有项目 XML。也可用 API 种子（RLDS 模板、不导入样例 json）：

```bash
LABEL_STUDIO_URL=http://127.0.0.1:8081/ LABEL_STUDIO_API_KEY=<token> LABEL_STUDIO_RLDS_CONFIG=1 \
  python3 docs/harness/overlays/zhiyuan-robot-video/seed_project.py
```

2–3 视角用 `configs/multi-view.xml`（本轮交互不改多视角）。

## 导入示例任务

Data Manager → Import，上传 `examples/tasks-single-view.json`。

官方发行版通常自带样例视频 `/static/samples/opossum_snow.mp4`。若打开任务 404，改成本地上传或可访问 URL。

任务 JSON 最小字段：

```json
[{ "video": "/static/samples/opossum_snow.mp4" }]
```

缺 `video` 的任务本 overlay 检查会拒绝。

## 导入 RLDS / TFRecord

Label Studio 不能直接播 TFRecord。Import 页可拖入 **完整 RLDS `1.0.0` 目录或 zip**（必须含 `dataset_info.json`、`features.json`、`*.tfrecord*`）。服务端只读解码，每个 episode 变成一条任务：`video` 指向生成的 `preview.mp4`，并带 `episode_id` / `source_type=rlds`。

- 不要只上传一个 `.tfrecord` shard。
- 不要和 mp4 / json 混在同一次导入里。
- 原始 TFRecord 不会被改写。同一 `episode_id` 再导会跳过。
- 一次最多导入 `RLDS_IMPORT_MAX_EPISODES` 条（默认 16）。
- zip 超过 250MB 时需要 `DATA_UPLOAD_MAX_MEMORY_SIZE`（启动脚本与 Dockerfile 已设为 1GB）。
- 自建镜像：官方 `latest` 是 **Alpine**，ffmpeg 用 `apk`。Alpine 自己的 Python 装不上 tensorflow；镜像里另嵌 **Debian Python 3.12 + TF**（`/opt/rlds/bin/python`）做解码。重建后 Docker 8080 可以导入 RLDS zip。本机源码跑：

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python --no-config --no-sources -e . \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
uv pip install --python .venv/bin/python --no-config --no-sources \
  -i https://pypi.tuna.tsinghua.edu.cn/simple tensorflow tensorflow-datasets Pillow
```

## 标注与提交

1. 把播放头停在阶段结束处，点顶部阶段标签。Regions 立即出现该段。片头、片尾都可以是 Static。
2. 选中右侧 Region，可改标签名（下拉）和起止帧。列表默认按点击顺序，先点的在上。
3. 整段选择细致度（简单 / 中等 / 复杂），填写动作序列。视频不可用时点顶部「废弃」。
4. 提交。同一视频做了两遍：两段都标，第一段复位放进该段的 `End`。



## 导出对账

1. Export 格式选 **JSON**。
2. 官方导出是 **task 数组**。对账读 `annotations[].result`。
3. 时间轴条目仍是 `ranges` + `timelinelabels`。废弃是：

```json
{
  "from_name": "discard",
  "to_name": "video",
  "type": "choices",
  "value": { "choices": ["废弃"] }
}
```

仓库夹具 `examples/annotation-export.json` 只示范阶段区间 + 细致度 / 动作序列；**不要把真实 Export 整包丢给** `check_overlay.py`。

## 检查

在仓库根目录：

```bash
python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py
python3 docs/harness/evals/test_robot_video_annotation.py
python3 docs/harness/evals/test_robot_video_ux.py
python3 docs/harness/evals/test_robot_video_rlds_decode.py
```

可选：`cd web && bun test --dom libs/editor/src/tags/control/__tests__/timelineClickToSpan.test.js`