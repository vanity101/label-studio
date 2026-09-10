# 智源标注平台（Label Studio）

访问地址：<http://192.168.110.23:8080/>

以 Docker 镜像运行，数据在宿主机 `~/zhiyuan-label-studio/data`。首次打开页面自行注册管理员账号。

## 容器

```bash
# 状态
docker ps -a --filter name=zhiyuan-ls

# 日志
docker logs -f zhiyuan-ls

# 重启
docker restart zhiyuan-ls
```

环境变量已写入容器：上传上限 1GB、关闭 GCE 探测、RLDS 单次最多 16 条 episode。换镜像后重建：

```bash
cd ~/zhiyuan-ls-build
docker build -f docs/harness/overlays/zhiyuan-robot-video/Dockerfile -t zhiyuan-label-studio:ux .
docker rm -f zhiyuan-ls
# 再执行 ~/zhiyuan-label-studio/run.sh
```

## 建项目并贴模板

1. Create Project，名称自定。
2. Labeling Setup → Code，粘贴本目录 `configs/` 里对应 XML 全文，Save。
3. 需要更多动作描述时：切到 Visual，在标签栏 Add。不要改四个阶段字面量的大小写：`Static` / `grasp` / `Place` / `End`。
4. 帧率必须与视频恒定帧率一致（10 / 15 / 25 / 30）。建议 MP4 + H.264。
   - 普通视频：`configs/single-view.xml`（默认 30fps）
   - RLDS / TFRecord 预览是 **10fps**：`configs/single-view-rlds.xml`
   - 2–3 视角结构：`configs/multi-view.xml`（镜头字段名以数据包为准）

## 标注规则（阶段标签）

- `Static`：第一帧到机械臂未触动之前；以及收回不动之后到最后一帧
- `grasp`：完全抓住物品、未抬起之前
- `Place`：放下物品，爪夹完全松开
- `End`：最后一个动作做完，收到不动状态

点顶部阶段标签即切段：第一段 start=1、end=播放头；其后 start=上一标签结束帧+1、end=播放头。播放头早于上一结束帧时允许重叠。不必再在时间轴上画。

「废弃」与阶段标签同一条顶部栏。点击表示当前视频不可用：不能再标阶段、不能再改已有区间；已有区间仍可见；仍可提交。废弃导出为整段 `choices`（`from_name=discard`），不是时间轴 `ranges`。

细致度（简单 / 中等 / 复杂）是同一条时间轴上标签多少、描述粗细，不是三套界面。

## 导入

- 普通任务：Data Manager → Import，可参考 `examples/tasks-single-view.json`。最小字段：`{"video": "<可访问的 mp4 URL 或本地上传>"}`。
- RLDS：拖入**完整** `1.0.0` 目录或 zip（必须含 `dataset_info.json`、`features.json`、`*.tfrecord*`）。不要只上传一个 shard，不要和 mp4/json 混导。每个 episode 变成一条任务，预览为 `preview.mp4`（10fps）。原始 TFRecord 只读；同一 `episode_id` 再导会跳过。

## 提交与导出

1. 播放头停在阶段结束处，点顶部阶段标签；右侧 Regions 可改名和起止帧；先点的在上。
2. 选细致度、填动作序列；不可用则点「废弃」。
3. 同一视频两段重复动作则两段都标，第一段复位放进该段的 `End`。
4. Export 选 **JSON**。官方导出是 task 数组，对账读 `annotations[].result`。时间轴是 `ranges` + `timelinelabels`。

员工培训手册（含截图）见 `使用手册.md` 与 `图片和附件/`。
