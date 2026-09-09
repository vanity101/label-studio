/**
 * Create Project Labeling Interface preset (DCP-37 / FR-014, FR-015, VIS-001, DEC-UI-002).
 * Literal XML from the issue body — not overlay single-view.xml (30fps).
 * Must persist on the project as label_config — Code editor-only is not enough.
 */
export const ROBOT_DEFAULT_TEMPLATE = `<View>
  <Header value="机器人视频时间轴标注"/>

  <View style="display:flex;flex-wrap:wrap;align-items:center;gap:8px">
    <TimelineLabels name="videoLabels" toName="video">
      <Label value="Static" background="#1d81cd"/>
      <Label value="grasp" background="#c813ec"/>
      <Label value="Place" background="#54d651"/>
      <Label value="End" background="#0d14d3"/>
    </TimelineLabels>
    <Choices name="discard" toName="video" choice="single" showInline="true">
      <Choice value="废弃"/>
    </Choices>
  </View>

  <Video name="video" value="$video" frameRate="10.0" timelineHeight="120"/>

  <Header value="信息复杂度"/>
  <Choices name="granularity" toName="video" choice="single" showInline="true">
    <Choice value="简单"/>
    <Choice value="中等"/>
    <Choice value="复杂"/>
  </Choices>
  <TextArea name="action_sequence" toName="video" editable="true" rows="2" placeholder="例如：抓住水瓶-倒水-放在桌上"/>
</View>`;

const EMPTY_VIEW = "<View></View>";

export function resolveCreateProjectLabelConfig(config) {
  const normalized = String(config ?? "").replace(/\s+/g, "");
  if (!normalized || normalized === EMPTY_VIEW) {
    return ROBOT_DEFAULT_TEMPLATE;
  }
  return config;
}
