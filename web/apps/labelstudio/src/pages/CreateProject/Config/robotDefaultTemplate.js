/**
 * Create Project Labeling Interface preset (DCP-55 / FR-001, FR-011, FR-019, ASM-001, ASM-004).
 * Five subtask labels + quality=0 axis; not overlay single-view.xml (30fps).
 */
export const ROBOT_DEFAULT_TEMPLATE = `<View>
  <Header value="机器人视频时间轴标注"/>

  <View style="display:flex;flex-wrap:wrap;align-items:center;gap:8px">
    <TimelineLabels name="videoLabels" toName="video">
      <Label value="Static" background="#1d81cd"/>
      <Label value="reach_object" background="#f59e0b"/>
      <Label value="grasp_object" background="#c813ec"/>
      <Label value="place_object" background="#54d651"/>
      <Label value="End" background="#0d14d3"/>
    </TimelineLabels>
    <TimelineLabels name="actionQuality" toName="video">
      <Label value="质量=0" background="#e11d48"/>
    </TimelineLabels>
    <Choices name="discard" toName="video" choice="single" showInline="true">
      <Choice value="废弃"/>
    </Choices>
  </View>

  <Video name="video" value="$video" frameRate="10.0" timelineHeight="120"/>
</View>`;
