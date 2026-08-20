# 智源机器人视频：RLDS / TFRecord 解码导入

本摘要叠加在 `zhiyuan-robot-video-annotation.md` 与 UX / 侍出各轮之上，**不取代**它们（一条时间轴、点标签切段、废弃、扁平拖排序、Vite 侍出）。

## 能力

在 Label Studio 的 **Import** 页上传完整 RLDS 数据集（`1.0.0` 目录或 zip），服务端只读打开 TFRecord，把每条 episode 物化为 H.264 `preview.mp4`（step 与帧 1:1，fps=10，`fps_assumed: true`），并建成一条带 `video` 字段的任务。标注仍用现有编辑器。

- 原始 TFRecord **只读、不改写**。
- 孤文件 `.tfrecord`（没有 `dataset_info.json` + `features.json`）必须失败，不假装解码成功。
- 同一项目再导入相同 `episode_id` 跳过，不建重复任务。
- 不另起 FastAPI 适配层；预览走官方 `/data/upload/...`。
- 不裁剪组织 / 分发任务等 LS 功能。

## 非目标

- 旁路 FastAPI、`POST /import-to-ls`、`export-to-silver` / Silver 契约
- 直读 TFRecord 当播放器、抽帧抽样
- 自动改项目 Labeling Config 的 `frameRate`（RLDS 预览是 10fps；请贴 `single-view-rlds.xml` 或把现有配置改成 10）
- 改切段公式、废弃、拖排序
- 删除 / 隐藏分发任务等 LS 功能
- 多视角三路验收、账号工作流

## 复用

[annotator-platform](https://github.com/vanity101/annotator-platform) 的 `tfds.builder_from_directory` + JPEG 序列 + ffmpeg 物化；现有 Import 文件夹拖入；官方 FileUpload / `/data/`；现有单视角时间轴模板。一键启动默认 `http://127.0.0.1:8081/`（仓库 `.venv`）。官方 `latest` 是 Alpine；Docker 8080 重建后用镜像内嵌的 Debian Python + TensorFlow 解码（不是另起 FastAPI）。

## 验收要点

合成 RLDS（1～2 条 episode）导入后任务数 = episode 数；每条有指向 mp4 的 `video`；`num_frames == len(steps)`；原 TFRecord 字节不变；缺元数据的孤文件失败；重复 `episode_id` 跳过。
