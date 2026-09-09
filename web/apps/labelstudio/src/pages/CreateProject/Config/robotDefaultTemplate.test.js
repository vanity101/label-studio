import { ROBOT_DEFAULT_TEMPLATE, resolveCreateProjectLabelConfig } from "./robotDefaultTemplate";

function normalizeXml(xml) {
  return xml.trim().replace(/\s+/g, " ");
}

describe("ROBOT_DEFAULT_TEMPLATE", () => {
  it("keeps DCP-37 stage labels, discard, granularity, and action_sequence", () => {
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="Static"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="grasp"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="Place"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="End"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="废弃"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="简单"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="中等"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="复杂"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="action_sequence"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="videoLabels"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="discard"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('name="granularity"');
  });

  it("uses frameRate 10.0 and timelineHeight 120, not overlay 30fps", () => {
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('frameRate="10.0"');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('timelineHeight="120"');
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain('frameRate="30');
    expect(ROBOT_DEFAULT_TEMPLATE).toContain('value="机器人视频时间轴标注"');
    expect(ROBOT_DEFAULT_TEMPLATE).not.toContain("单视角");
  });

  it("matches SRC-002 structure after whitespace normalization (VIS-001)", () => {
    const expected = `<View>
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

    expect(normalizeXml(ROBOT_DEFAULT_TEMPLATE)).toBe(normalizeXml(expected));
  });
});

describe("resolveCreateProjectLabelConfig", () => {
  it("replaces missing or empty View so Import-first Save still persists the preset", () => {
    expect(resolveCreateProjectLabelConfig(undefined)).toBe(ROBOT_DEFAULT_TEMPLATE);
    expect(resolveCreateProjectLabelConfig("")).toBe(ROBOT_DEFAULT_TEMPLATE);
    expect(resolveCreateProjectLabelConfig("<View></View>")).toBe(ROBOT_DEFAULT_TEMPLATE);
    expect(resolveCreateProjectLabelConfig("  <View></View>  ")).toBe(ROBOT_DEFAULT_TEMPLATE);
  });

  it("leaves a non-empty labeling config unchanged", () => {
    const custom = "<View><Text name=\"t\" value=\"$text\"/></View>";
    expect(resolveCreateProjectLabelConfig(custom)).toBe(custom);
  });
});
