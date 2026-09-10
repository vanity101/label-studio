# 智源：LeRobot 导入（给实现 agent 的参考）

本文给 **multica / 实现 agent** 用。不要另开 FastAPI，不要走 RLDS / TFRecord。在现有 `label_studio/robot_import/` 上加 LeRobot 适配器，复用「检测 → 独立进程物化 `preview.mp4` → 一条任务」。

人只确认验收，不代替 Verify。改 Import 页或标注页后必须：Playwright MCP 登录后点关键路径并截图；跑 `python3 docs/harness/evals/test_robot_video_ux_runtime.py`。docker / curl / 源码 grep 不算完成。禁止请人强刷或自己点页面。

装依赖必须带国内镜像，禁止先跑官方源。见仓库 `AGENTS.md` 与 `.cursor/rules/domestic-mirrors.mdc`。`pyarrow` / `h5py` 用清华 PyPI；`uv` 必须 `--no-config --no-sources`。

---

## 背景（已经做完的）

产品数据面 **只认 HDF5 + 后续 LeRobot**，不使用 RLDS。

HDF5 已落地：Import 上传 YAM schema v3 的一集目录 / 多集 zip / 最小包（`info.yaml` + `high_cam.hdf5`）后，worker 逐帧读 `high_cam` 的 `rgb/data`，ffmpeg 编 30fps H.264，每集一条任务。

| 字段 | HDF5 现状 |
| --- | --- |
| `video` | FileUpload 后的 `*-preview.mp4` URL |
| `episode_id` | 目录名，如 `episode_000000` |
| `source_type` | `yam_hdf5` |
| `camera` | `high_cam` |
| `num_frames` | RGB 帧数 T |
| `fps` | `rgb.attrs requested_hz`，样本为 30 |
| `fps_assumed` | `false` |

标注仍用 overlay 模板 `docs/harness/overlays/zhiyuan-robot-video/configs/single-view.xml`（`frameRate=30`）。阶段标签：`Static` / `grasp` / `Place` / `End`。点标签切段，不要改交互。

本轮 **只补 LeRobot**。不要重做切段 / 废弃 / 拖排序，不要做三路预览、depth、关节上时间轴。

---

## 为什么这份 LeRobot 现在不能播

样本在服务器（**不含** 用户自己抽的 `images/`）：

`ubuntu@192.168.110.23:/home/eisoc/RLinf/data/RLinf/0907_test2`

同机还有 YAM HDF5：`/data/0907_test2`，不要和 LeRobot 包搞混。拉到本地任意目录即可。

| 事实 | 含义 |
| --- | --- |
| LeRobot **v2.1**（`meta/info.json` `codebase_version`） | 锁这份样本，不要先做 v3 新布局 |
| `total_videos: 0`，`video_path: null` | 没有可直接侍出的 mp4 |
| 只有 `data/` + `meta/` | 相机在 parquet 里 |
| `data/chunk-000/episode_000000.parquet` ≈ 1.1GB | 470 行；三路 RGB + depth + 关节 |
| `observation.images.high_cam` 等 | Arrow `struct<bytes: binary, path: string>`，每帧一张压缩图 |
| `images/` | 用户预览用静图，**检测和物化都忽略，不要下载也不要上传** |
| 标注页 `<Video>` | 只认 HTTP 上的 mp4/webm，打不开 parquet |

所以方案不是「让播放器读 parquet」，而是和 HDF5 一样 **编 `preview.mp4` 再播**。

`info.json` 关键字段（已核实）：

- `total_episodes`: 1
- `total_frames`: 470
- `fps`: 30
- `data_path`: `data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet`
- 图像特征：`observation.images.high_cam`（480×848×3）、`l_cam` / `r_cam`（530×848×3）
- 默认只用 **high_cam**，与 HDF5 一致

---

## 目标行为

用户在 Import 上传 **LeRobot 数据集根**（或 zip / 最小包）后：

1. 每个 episode 一条任务，能在标注页播预览视频。
2. 默认头顶相机 `high_cam`，帧率读 `info.json` 的 `fps`（这份是 30，`fps_assumed=false`）。
3. 原始 parquet / json **只读、不改写**。
4. 同项目重复 `episode_id` 跳过。
5. 一次最多 `ROBOT_IMPORT_MAX_EPISODES`（默认 16）。
6. 不能与 YAM HDF5、裸 mp4、普通 json 任务文件混传。
7. 上传物里的 `images/`、`*-preview.mp4` 一律忽略。

任务字段：

```json
{
  "data": {
    "video": "<FileUpload preview url>",
    "episode_id": "episode_000000",
    "source_type": "lerobot",
    "camera": "high_cam",
    "num_frames": 470,
    "fps": 30,
    "fps_assumed": false
  }
}
```

`episode_id` = `episode_{episode_index:06d}`，与 `meta/episodes.jsonl` / parquet 的 `episode_index` 一致。

---

## 用户怎么传

合法输入（任一）：

- 数据集根目录：含 `meta/info.json` + `data/**/*.parquet`
- 上述目录的 zip
- 最小包：`meta/info.json` + 对应 parquet（可无 `videos/`、必须无混传）
- 若有 `videos/`：一并上传更好（见解码优先级），但仍不要带 `images/`

Import 扩展名需能选中：现有 robot 为 `zip, hdf5, h5, yaml, yml`。本轮加上 **`json`、`parquet`**。注意：`json` 已在 structuredData 里；检测必须靠 **整批文件组合** 判断是 LeRobot 还是普通 JSON 任务，单靠扩展名不够。

文案改掉 “LeRobot will be added later”。说明：YAM HDF5 与 LeRobot 分两次传；LeRobot 预览默认 high_cam；不要带 `images/`。

---

## 检测规则

改 `label_studio/robot_import/detect.py`。`classify_upload_names` 现只返回 `yam_hdf5 | mixed | other`，改为：

`yam_hdf5 | lerobot | mixed | other`

判断（先丢掉 `images/**` 与 `*-preview.mp4`）：

| 批次内容 | 结果 |
| --- | --- |
| `info.yaml`/`yml` + `high_cam.hdf5`/`h5`（可加 zip） | `yam_hdf5` |
| `meta/info.json`（或 basename `info.json` 且同批有 parquet）+ `.parquet`（可加 zip / `videos/**`） | `lerobot` |
| 同时像 YAM 又像 LeRobot | `mixed` → ValidationError |
| LeRobot 或 YAM 再加裸 mp4 / 普通任务 json（非 `meta/info.json`） | `mixed` |
| 只有孤 parquet、只有 `info.json`、只有 `images/` | 失败，错误信息写清缺什么 |
| 其它 | `other`（走官方导入，本拦截返回 `None`） |

磁盘上认定 LeRobot 根目录：存在 `meta/info.json`，且 `data/` 下至少有一个 `.parquet`。zip 解压后对根或唯一子目录做同样检查。

YAM 的 `require_yam_episodes` 不要误伤 LeRobot（LeRobot 的 `info.json` ≠ YAM 的 `info.yaml`）。

---

## 解码优先级（必须按这个顺序）

默认相机特征名：`observation.images.high_cam`。相机短名：`high_cam`。

对每个 episode：

1. **已有视频**：`info.json` 的 `video_path` 非空，且能解析出该集 high_cam（或唯一）mp4，文件存在 → **直接用该 mp4**，不重编。`num_frames` 用 ffprobe，对不上 `episodes.jsonl` 的 `length` 时以视频帧数为准并打日志，不要静默失败。
2. **parquet 图像列**：打开该集 parquet，**只读** `observation.images.high_cam`（没有则失败，不要悄悄改用 l_cam）。按 batch 迭代，把每行 `bytes` 写成 JPEG，再走现有 ffmpeg（`materialize._encode_mp4`，pad 偶数边、yuv420p、faststart）。`fps` = `info.json.fps`，缺省才 30 且 `fps_assumed=true`。
3. 两样都没有 → `RobotImportError`，文案写明「没有 videos/ 也没有 observation.images.high_cam」。

这份 `0907_test2` 走规则 2。

### 内存硬约束

单集 parquet 1.1GB，里面还有 depth。

- 用 `pyarrow.parquet.ParquetFile.iter_batches`，`columns=["observation.images.high_cam"]`。
- **禁止** `pq.read_table` 整表，禁止 pandas，禁止读 depth / 其它相机。
- `bytes` 用 Pillow 打开再存 JPEG（质量与 HDF5 路径一致即可，现为 95）。
- 与 HDF5 一样：逐帧写临时目录，编完删临时帧。

### 依赖

- 新增：`pyarrow`（清华镜像）。
- 已有：Pillow、ffmpeg/ffprobe、独立 worker（`ROBOT_IMPORT_PYTHON` 或 `RLDS_PYTHON` 或 `sys.executable`）。
- Overlay Dockerfile / `start_label_studio.py` 的 Debian Python 环境也要装 `pyarrow`，否则 Docker :8080 只能导 HDF5。
- `require_pyarrow()` 仿 `require_h5py()`，缺依赖抛 `RobotDependencyError`（HTTP 503）。

---

## 代码落点（少改、对齐现有）

包：`label_studio/robot_import/`（已声明「HDF5 与后续 LeRobot 共用管道」）。

| 文件 | 做什么 |
| --- | --- |
| `detect.py` | 识别 lerobot；忽略 `images/`；zip/json/parquet 文件名 |
| **新建** `lerobot.py` | 列 episode、解析 `info.json`、抽帧迭代器 |
| `materialize.py` | 抽帧接口泛化（HDF5 与 LeRobot 都能喂 JPEG 序列）；已有 mp4 则 skip encode |
| `import_batch.py` | 按 bronze 根类型分发；任务 `source_type=lerobot` |
| `worker.py` | 同一 CLI，不要第二个 worker |
| `ls_import.py` | `classify` 后两条路径；成功返回的 fields 仍含 `video` / `episode_id` / `source_type` |
| `stage.py` | 解压/拼目录后既能 `require_yam_episodes` 也能认 LeRobot 根 |
| `Import.jsx` | 扩展名 + 文案 |
| Overlay `Dockerfile` / `start_label_studio.py` | 装 pyarrow；上传上限保持 8GB |
| Overlay `README.md` | 增加 LeRobot 导入一节，删「后续再接」 |

不要新建旁路服务。不要改 `single-view.xml` 的标签字面量。`frameRate` 已是 30，与这份数据一致。

`decode_bronze_to_tasks_isolated` 超时已是 3600s。470 帧编 mp4 应远小于此；仍要避免把 1.1GB 一次性读进内存导致 OOM。

---

## 明确不做

- RLDS / TFRecord 产品路径
- 三路预览、depth、关节时间轴
- 改切段 / 废弃 / 拖排序
- 把 `images/` 当数据源
- 为「能播」去改 LSF Video 组件读 parquet
- 本轮做完整 LeRobot v3 / HuggingFace `src` 布局（若上传物已有 `videos/*.mp4`，规则 1 自然覆盖）
- 服务端任意本地路径扫描（除非现有 HDF5 已有且你只是复用；没有就不要新开口子）

---

## Eval 与核验（合同）

新建：

- `docs/harness/product-specs/zhiyuan-lerobot-import.md`（本文件）
- `docs/harness/evals/robot-video-lerobot-import.md`（短合同：MUST 条）
- `docs/harness/evals/test_robot_video_lerobot_import.py`

合成夹具（不要用 1.1GB 真包当单测）：

- 写 3～4 帧很小的 JPEG（建议 ≥180×320，避免再出现 16×24「色块」误判）
- 打进 parquet 的 `observation.images.high_cam`
- 最小 `meta/info.json`（v2.1，`fps=30`，`video_path=null`）
- 断言：检测为 `lerobot`；任务数=episode 数；`num_frames` 对；产出 mp4；孤 parquet 失败；与 hdf5 混传失败；`images/` 被忽略；重复 `episode_id` 跳过

真机核验（改了 Import / 标注侍出则必须）：

1. 本机 LS：`start_label_studio.py --local --port 8081`。注意 **8080 经常是 SSH 转发，不是本机 LS**。
2. 登录后的应用页（未登录登录页不算）。本机核验账号曾用 `rlds-verify@localhost` / `rldsverify123`。
3. Import 从服务器拉下来的 LeRobot 目录（或打成不含 `images/` 的 zip）。
4. 打开任务：必须是俯视工作台实景，不是纯色块；时间轴能到 `1 of 470`（或物化后的帧数）。
5. **真实点击 Place**，看到时间轴/Regions 出现 Place 段。
6. `LABEL_STUDIO_URL=http://127.0.0.1:8081` 且 `env -u HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY`，用 **仓库 `.venv/bin/python`** 跑：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY \
  LABEL_STUDIO_URL=http://127.0.0.1:8081 \
  LABEL_STUDIO_EVAL_EMAIL=rlds-verify@localhost \
  LABEL_STUDIO_EVAL_PASSWORD=rldsverify123 \
  .venv/bin/python \
  docs/harness/evals/test_robot_video_ux_runtime.py
```

系统 Python 的 Playwright 可能缺 Chromium，不要用。

`test_robot_video_ux_runtime.py` 的 LIVE 默认是 `:8080`，必须以环境变量指到正在跑、且已打进本轮前端的实例。

---

## 运维备忘（实现时容易踩）

- 启动：`python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py --local --port 8081`。不要仓库根目录 `docker-compose up`。
- 健康检查若走系统代理 `127.0.0.1:1080` 会 ENV_FAIL，用 `curl --noproxy '*'`。
- 远程 Docker `zhiyuan-label-studio:ux` **不会自动有本轮代码**，要 `--build --recreate` 之后 192.168.110.23:8080 才有 LeRobot。
- 远程 SSH：`ubuntu@192.168.110.23`（历史 askpass 密码 `1`）。LeRobot 在 `eisoc` 家目录，ubuntu 只读即可。
- 拉数据（排除 images）：

```bash
rsync -avP --exclude 'images/' --exclude 'images' \
  ubuntu@192.168.110.23:/home/eisoc/RLinf/data/RLinf/0907_test2/ \
  ./lerobot_0907_test2/
```

- 先前项目 `hdf5-eval` 里是合成 24×16 色块，**不是**解码失败。核验请用新项目或 `yam-high-cam` / 新的 LeRobot 项目。

---

## 建议实现顺序

1. 检测 + 合成夹具 eval（红）。
2. `lerobot.py` 抽帧 + materialize（夹具绿）。
3. 接到 `import_batch` / `ls_import` / Import 文案。
4. Dockerfile / start 脚本装 pyarrow。
5. 浏览器导入拉下来的 LeRobot 目录，点 Place，跑 UX runtime eval。
6. 更新 overlay README。

没有完成检测/物化合同之前，不要改标注业务交互。
