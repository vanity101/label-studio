import { observer } from "mobx-react";
import { types } from "mobx-state-tree";

import Registry from "../../core/Registry";
import { guidGenerator } from "../../core/Helpers";
import SelectedModelMixin from "../../mixins/SelectedModel";
import ControlBase from "./Base";
import { HtxLabels, LabelsModel } from "./Labels/Labels";
import {
  canCreateSpan,
  DISCARD_LABEL,
  lastCreatedTimelineRegion,
  nextClickSpan,
  resolveNamedTag,
} from "./timelineClickToSpan";

/**
 * Use the TimelineLabels tag to classify video frames. This can be a single frame or a span of frames.
 *
 * First, select a label and then click once to annotate a single frame. Click and drag to annotate multiple frames.
 *
 * ![Screenshot of video with frame classification](../images/timelinelabels.png)
 *
 * Use with the `<Video>` control tag.
 *
 * !!! info Tip
 *     You can increase the height of the timeline using the `timelineHeight` parameter on the `<Video>` tag.
 *
 * @example
 * <View>
 *   <Header>Label timeline spans:</Header>
 *   <Video name="video" value="$video" />
 *   <TimelineLabels name="timelineLabels" toName="video">
 *     <Label value="Nothing" background="#944BFF"/>
 *     <Label value="Movement" background="#98C84E"/>
 *   </TimelineLabels>
 * </View>
 * @name TimelineLabels
 * @regions TimelineRegion
 * @meta_title TimelineLabels tag
 * @meta_description Classify video frames using TimelineLabels.
 * @param {string} name Name of the element
 * @param {string} toName Name of the video element
 */
const TagAttrs = types.model({
  toname: types.maybeNull(types.string),
});

const ModelAttrs = types.model("TimelineLabelsModel", {
  pid: types.optional(types.string, guidGenerator),
  type: "timelinelabels",
});

const ClickToSpan = types.model("TimelineLabelsClickToSpan").actions((self) => ({
  /**
   * Clicking a phase label creates a span immediately.
   * @returns {boolean} true if the click was handled (skip default toggleSelected)
   */
  handleLabelClick(label) {
    if (!label || label.value === DISCARD_LABEL) return false;

    const video =
      resolveNamedTag(self.annotation, self.toname) ||
      (self.annotation?.objects ?? []).find((tag) => tag?.type === "video");
    if (!video) return false;
    if (!canCreateSpan(Boolean(video.isDiscarded))) return true;

    const last = lastCreatedTimelineRegion(self.annotation.regionStore?.regions ?? []);
    const span = nextClickSpan(last?.ranges?.[0]?.end, video.currentFrame ?? video.frame ?? 1);

    self.annotation.unselectAreas?.();
    self.unselectAll();
    label.setSelected(true);
    const region = video.addTimelineRegion({ frame: span.start });
    if (region) {
      region.setRange([span.start, span.end], { mode: "new" });
    }
    self.unselectAll();
    return true;
  },
}));

const TimelineLabelsModel = types.compose(
  "TimelineLabelsModel",
  ControlBase,
  LabelsModel,
  ModelAttrs,
  TagAttrs,
  SelectedModelMixin.props({ _child: "LabelModel" }),
  ClickToSpan,
);

const HtxTimelineLabels = observer(({ item }) => {
  return <HtxLabels item={item} />;
});

Registry.addTag("timelinelabels", TimelineLabelsModel, HtxTimelineLabels);

export { HtxTimelineLabels, TimelineLabelsModel };
