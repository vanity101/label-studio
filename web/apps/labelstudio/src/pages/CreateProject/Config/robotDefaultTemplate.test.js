import { ROBOT_DEFAULT_TEMPLATE } from "./robotDefaultTemplate";

function normalizeXml(xml) {
  return xml.trim().replace(/\s+/g, " ");
}

describe("ROBOT_DEFAULT_TEMPLATE", () => {
  it("uses the five contract subtask labels, discard, and quality=0 axis", () => {
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="Static"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="reach_object"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="grasp_object"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="place_object"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="End"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="废弃"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="质量=0"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="videoLabels"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="actionQuality"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="discard"');
    const labelValues = [...ROBOT_DEFAULT_TEMPLATE.matchAll(/value="([^"]+)"/g)].map((m) => m[1]);
    expect(labelValues).not.toContain("grasp");
    expect(labelValues).not.toContain("Place");
  });

  it("drops granularity and action_sequence", () => {
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("granularity");
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("action_sequence");
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("信息复杂度");
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("细致度");
  });

  it("uses frameRate 10.0 and timelineHeight 120, not overlay 30fps", () => {
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('frameRate="10.0"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('timelineHeight="120"');
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain('frameRate="30');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="机器人视频时间轴标注"');
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("单视角");
  });

  it("matches the DCP-55 preset XML after whitespace normalization", () => {
    const expected = `<View>
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

    expect(normalizeXml(ROBOT_DEFAULT_TEMPLATE)).toBe(normalizeXml(expected));
  });
});
