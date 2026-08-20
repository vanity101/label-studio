# Problem

智源标注要直接吃 Open X / RLDS 的 TFRecord，但 Label Studio 只能播 mp4。旁路仓库 [annotator-platform](https://github.com/vanity101/annotator-platform) 已有只读物化（`materialize` → `preview.mp4`），本仓库标注交互已能用，两边还没接上：标注员仍须先在仓外转出 mp4 再 Import。

本轮叠加在 overlay / UX / 侍出之上，**不取代**它们。不裁剪 LS 分发任务等功能。目标：在本进程嵌入解码器，Import 页上传完整 RLDS 目录或 zip 后，每个 episode 变成一条可标任务。

必须纠正：

- 不要把单个 `.tfrecord` shard 当成一条媒体任务。
- 不要另起 FastAPI `:8000` 或第二套标注 UI。
- 不要改写 Bronze TFRecord。
- 不要抽帧抽样（必须 step:帧 1:1）。
- 不要为做解码器而拆掉已验收的切段 / 废弃 / 拖排序。

# Users and Context

- **标注员 / 项目负责人**：在现有项目 Import 里拖入 RLDS `1.0.0` 文件夹或 zip（须含 `dataset_info.json`、`features.json`、`*.tfrecord*`），等待解码后在 Data Manager 看到视频任务，按既有时间轴交互标注。
- **下游**：任务 `data` 含 `video`（可播 mp4 URL）、`episode_id`、`source_type=rlds`。导出形状仍是官方 Annotation。
- **本仓库 Agent**：可以改 `label_studio/` 导入路径与新增 `rlds_decode` 库、浅改 Import 页；没有完成合同不得改业务代码。禁止重写编辑器，禁止把 Silver 契约搬进本轮。

产品事实（不要再猜）：

1. 数据源是 **完整 RLDS 数据集目录或 zip**，不是孤 TFRecord。
2. 物化：`observation.image`，step 与帧 1:1，ffmpeg H.264，fps=10，`fps_assumed: true`。
3. 一条 episode 对应一条 LS Task；`video` 指向 `/data/upload/.../preview.mp4`。
4. 原 TFRecord 只读。同一 `episode_id` 再导入跳过。
5. 本轮不自动改项目 XML 的 `frameRate`。提供 `configs/single-view-rlds.xml`（仅 frameRate=10）。

# Deliverables

1. 本文件 + 稳定摘要 `docs/harness/product-specs/zhiyuan-rlds-decode.md`。
2. 库 `label_studio/rlds_decode/`：列举、物化、拼 Bronze、生成任务（移植适配层逻辑，去掉 FastAPI）。
3. Django Import 拦截：RLDS 批次走解码；mp4 / json 仍走原路径。
4. Import 页：放行 zip / tfrecord 文件名，并写清「完整目录或 zip」。
5. overlay：`single-view-rlds.xml`、README、`start_label_studio.py`（默认本机 `http://127.0.0.1:8081/`；Docker 用 `--docker`，8080 重建后以内嵌 Debian Python+TF 解码）。自建镜像用 Alpine `apk` 装 ffmpeg。
6. 完成合同与 eval（本轮实现前必须先有合同文件）。

# Success Criteria

以下任一项不满足，本轮即未完成：

- 合成 RLDS 导入后任务数 = episode 数（受 `RLDS_IMPORT_MAX_EPISODES` 上限约束，默认 16）。
- 每条任务有 `video`（mp4 URL）、`episode_id`、`source_type=rlds`。
- 物化后 `num_frames == len(steps)`；原 TFRecord 字节不变。
- 缺 `dataset_info.json` / `features.json` 的孤 tfrecord 导入失败，错误信息明确。
- 同一项目再导入同一 `episode_id` 不建重复任务。
- 非 RLDS 导入（mp4 / json）行为不变。
- 上一轮 overlay / UX / runtime / reorder / dm-user-ref eval 仍绿。
- 不出现旁路 FastAPI 服务、不改切段公式。

# Out of Scope

- `export-to-silver`、旁路 `POST /import-to-ls`、独立适配层进程。
- 直读 TFRecord 播放、抽帧抽样、多路相机。
- 自动改已有项目的 Labeling Config。
- 删除 / 隐藏组织、分发、Label Stream。
- 多视角验收、账号工作流、Silver 训练契约。

# Existing Building Blocks

- annotator-platform：`rlds.py`、`materialize.py`、合成 RLDS 夹具。
- LS：`data_import.uploader` / `FileUpload.load_tasks_from_uploaded_files`；Import 页 `traverseFileTree`；`FileUpload` + `/data/`。
- overlay 单视角模板与自建镜像 Dockerfile。

# High-Level Approach

1. 先合同后实现。
2. 解码是本进程库，不是第二套产品。
3. 以「批次像不像完整 RLDS」分流；像则解码，不像则原导入。
4. zip 仅用于 RLDS；随机 zip 必须失败而不是变成一条未定义媒体任务。
5. 缺 tensorflow / ffmpeg 时导入失败并说明安装 `[rlds]` 与 ffmpeg，不假装成功。

# Risks

- `os.path.splitext` 无法识别 `*.tfrecord-00000-of-00001`：必须按文件名子串判断。
- 整集 fridge（数十条）同步导入会超时：默认上限 16，可用环境变量加大。
- 项目 XML `frameRate=30` 与 RLDS 预览 10fps 错位：本轮用单独配置 + 说明，不自动改 XML。
- tensorflow 体积大：只放 optional extra，默认 pip 不装。

# Suggested Verification

- 合成 RLDS 夹具（不依赖真实 Bronze）：列举、物化帧数、TFRecord 指纹不变、孤文件拒绝、重复 id 跳过。
- 源码约束：导入路径调用 `rlds_decode`；Import.jsx 放行 zip/tfrecord；Dockerfile 含 ffmpeg。
- 旧 eval 全绿。
- 缺 tensorflow / ffmpeg：物化相关检查失败并写明原因，禁止 skip 装绿。
