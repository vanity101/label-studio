# Contract: 智源机器人视频（RLDS / TFRecord → MP4 导入）

本轮按 `docs/harness/exec-plans/active/label-studio-rlds-decode.md` 交付。叠加在 overlay / UX / 侍出 / 拖排序之上，不取代它们。

允许改 `label_studio/rlds_decode/`、`label_studio/data_import/`、`label_studio/core/settings/base.py`、Import 页、overlay 配置与 Dockerfile。禁止重写编辑器，禁止旁路 FastAPI，禁止改切段公式。

## Deliverables

- `label_studio/rlds_decode/`：只读列举 + 物化 + 拼 Bronze + 生成任务
- Import 拦截：完整 RLDS 目录/zip → 每 episode 一条 `video` 任务；mp4/json 原路径不变
- Import 页放行 zip / tfrecord 文件名，并说明须完整数据集
- `configs/single-view-rlds.xml`（frameRate=10）与 README / `start_label_studio.py`（默认本机 `:8081`、1GB 上传、`NO_GCE_CHECK`）/ 镜像 ffmpeg + `[rlds]` extra
- 本文件对应的 eval

## Verification

- overlay：`python3 docs/harness/overlays/zhiyuan-robot-video/check_overlay.py`
- 旧 eval 仍须绿：
  - `python3 docs/harness/evals/test_robot_video_annotation.py`
  - `python3 docs/harness/evals/test_robot_video_ux.py`
  - `python3 docs/harness/evals/test_robot_video_ux_runtime.py`（live 首页项打 `http://127.0.0.1:8081/`；无服务时按该文件既有规则）
  - `python3 docs/harness/evals/test_robot_video_ux_reorder.py`
  - `python3 docs/harness/evals/test_robot_video_dm_user_ref.py`
- 本轮：`python3 docs/harness/evals/test_robot_video_rlds_decode.py`（若系统 Python 无 tensorflow，eval 会改用仓库 `.venv`；也可直接 `.venv/bin/python docs/harness/evals/test_robot_video_rlds_decode.py`）
- 上游 Cypress / 全仓 build：不是本轮通过条件
- 自建镜像实际 `docker build`：本机依赖不足时报告 ENV，不把本轮判为合同失败（Dockerfile 必须含 ffmpeg 与 rlds extra）

## Hard thresholds

- 本轮 eval 全绿；`pass_rate >= 0.8` 且无 Critical
- 合成 RLDS（eval 夹具，不依赖真实 Bronze）物化后 `num_frames == len(steps)`，预览为 mp4
- 物化前后 Bronze 下 `*.tfrecord*` 的 sha256 不变
- 孤 tfrecord（无 `dataset_info.json` / `features.json`）必须失败，错误含「dataset_info」或「features」
- 已存在的 `episode_id` 再次生成任务列表时被跳过（任务数不增加）
- 生成的任务 `data` 含 `video`（以 `.mp4` 结尾）、`episode_id`、`source_type=rlds`
- zip / 目录拼出的 Bronze 能被识别为 RLDS；随机 zip（无元数据）失败
- `Import.jsx` 放行 zip 与文件名含 `.tfrecord` 的文件
- overlay Dockerfile 仍 `FROM heartexlabs/label-studio`，用 `apk add ffmpeg`；用 Debian `python:3.12-slim-bookworm` 阶段安装 tensorflow，经 `RLDS_PYTHON` 在 Alpine 里跑解码 worker。禁止 runtime 阶段 `apt-get`。并设 `DATA_UPLOAD_MAX_MEMORY_SIZE` / `NO_GCE_CHECK`；`pyproject.toml` 有 optional extra `rlds`
- `start_label_studio.py` 默认打开 `http://127.0.0.1:8081/`（本机 `.venv`），并注入上述环境变量；Docker 用 `--docker`
- `configs/single-view-rlds.xml` 通过单视角检查且 `frameRate` 为 10
- 不出现 FastAPI 适配层服务代码作为本轮导入路径
- 切段 / 废弃 / 拖排序源码仍在（旧 eval 锁住）

## 合同写死的边界行为

- 缺 tensorflow / ffmpeg：物化相关测试 **失败** 并写明安装方式（清华镜像 pip / 系统 ffmpeg），禁止 `skip` 装绿
- RLDS 与 mp4/json **混传** 必须失败，不得 silently 丢掉一半
- zip 仅用于 RLDS；不能当「一条未定义媒体任务」导入
- `RLDS_IMPORT_MAX_EPISODES` 默认 16；超出的 episode 不导入（不崩溃）
- 本轮不自动改已有项目 Labeling Config
- 不改写 TFRecord；不抽帧抽样

## Failure behavior

- 无法解码时返回明确错误（缺元数据、缺依赖、ffmpeg 失败、混传）
- 禁止把每个 tfrecord shard 变成一条任务
- 禁止编造 Silver 字段或秒↔帧换算
- 禁止为解码器重写 LSF 播放器
