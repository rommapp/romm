<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type {
  ChannelSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import { formatRelativeDate } from "@/utils";
import { useDeviceLabel } from "@/v2/composables/useDeviceLabel";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  channels: ChannelSchema[];
  /** Each channel's history, newest first, keyed by channel id. */
  histories: Record<string, SnapshotSchema[] | null>;
  legacySaves: Record<string, SaveSchema[]>;
}>();

const emit = defineEmits<{
  openSnapshot: [channel: ChannelSchema, snapshot: SnapshotSchema];
  openSave: [channel: ChannelSchema, save: SaveSchema];
}>();

const { t } = useI18n();
const deviceLabel = useDeviceLabel();

const LANE_COLORS = [
  "var(--r-color-brand-primary)",
  "var(--r-color-brand-accent)",
  "var(--r-color-success)",
  "var(--r-color-info)",
];
const LANE_W = 34;
const ROW_H = 46;
const LEFT = 20;
const TOP = 22;

interface Node {
  key: string;
  lane: number;
  channel: ChannelSchema;
  snapshot: SnapshotSchema | null;
  save: SaveSchema | null;
  at: number;
  x: number;
  y: number;
}

const nodes = computed<Node[]>(() => {
  const unplaced = props.channels.flatMap((channel, lane) => [
    ...(props.histories[channel.id] ?? []).map((snapshot) => ({
      key: `s-${snapshot.id}`,
      lane,
      channel,
      snapshot,
      save: null,
      at: Date.parse(snapshot.created_at),
    })),
    ...(props.legacySaves[channel.id] ?? []).map((save) => ({
      key: `l-${save.id}`,
      lane,
      channel,
      snapshot: null,
      save,
      at: Date.parse(save.updated_at),
    })),
  ]);
  return unplaced
    .sort((a, b) => b.at - a.at)
    .map((node, row) => ({
      ...node,
      x: LEFT + node.lane * LANE_W,
      y: TOP + row * ROW_H,
    }));
});

const textX = computed(() => LEFT + props.channels.length * LANE_W + 12);
const height = computed(() => TOP + nodes.value.length * ROW_H);

const bySnapshotId = computed(
  () =>
    new Map(
      nodes.value.filter((n) => n.snapshot).map((n) => [n.snapshot!.id, n]),
    ),
);

const rails = computed(() =>
  props.channels.map((channel, lane) => {
    const ys = nodes.value.filter((n) => n.lane === lane).map((n) => n.y);
    return {
      key: channel.id,
      x: LEFT + lane * LANE_W,
      y1: Math.min(...ys),
      y2: Math.max(...ys),
      color: LANE_COLORS[lane % LANE_COLORS.length],
      dashed: !channel.current,
      visible: ys.length > 0,
    };
  }),
);

const edges = computed(() =>
  nodes.value.flatMap((node) => {
    const parentId = node.snapshot?.parent_snapshot_id;
    const parent = parentId ? bySnapshotId.value.get(parentId) : undefined;
    if (!parent || !node.snapshot) return [];
    const midY = (parent.y + node.y) / 2;
    return [
      {
        key: `${parent.key}-${node.key}`,
        d: `M${parent.x},${parent.y} C${parent.x},${midY} ${node.x},${midY} ${node.x},${node.y}`,
        color: LANE_COLORS[node.lane % LANE_COLORS.length],
        branch: node.snapshot.kind === "branch",
      },
    ];
  }),
);

function isCurrent(node: Node): boolean {
  return node.snapshot?.id === node.channel.current_snapshot_id;
}

function headline(node: Node): string {
  const parts = [node.channel.label];
  if (isCurrent(node)) parts.push(t("channels.current"));
  if (node.snapshot?.kind === "branch") parts.push(t("channels.branch"));
  if (node.snapshot?.is_pinned) parts.push(t("channels.pinned"));
  if (node.save) parts.push(t("channels.legacy-save"));
  return parts.join(" · ");
}

function detail(node: Node): string {
  return node.snapshot
    ? `${formatRelativeDate(node.snapshot.created_at)} · ${deviceLabel(node.snapshot.device)}`
    : formatRelativeDate(node.save!.updated_at);
}

function open(node: Node) {
  if (node.snapshot) emit("openSnapshot", node.channel, node.snapshot);
  else if (node.save) emit("openSave", node.channel, node.save);
}

function onKey(event: KeyboardEvent, node: Node) {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  open(node);
}
</script>

<template>
  <div class="r-channel-timeline" v-bind="$attrs">
    <svg
      :width="textX + 340"
      :height="height"
      :viewBox="`0 0 ${textX + 340} ${height}`"
      role="group"
      :aria-label="t('channels.timeline-label')"
    >
      <line
        v-for="rail in rails.filter((r) => r.visible)"
        :key="rail.key"
        :x1="rail.x"
        :x2="rail.x"
        :y1="rail.y1"
        :y2="rail.y2"
        :stroke="rail.color"
        stroke-opacity="0.35"
        stroke-width="2"
        :stroke-dasharray="rail.dashed ? '3 4' : undefined"
      />
      <path
        v-for="edge in edges"
        :key="edge.key"
        :d="edge.d"
        fill="none"
        :stroke="edge.color"
        stroke-width="2"
        :stroke-dasharray="edge.branch ? '4 4' : undefined"
        :stroke-opacity="edge.branch ? 0.6 : 1"
      />
      <g
        v-for="node in nodes"
        :key="node.key"
        class="r-channel-timeline__node"
        role="button"
        tabindex="0"
        :aria-label="`${headline(node)}, ${detail(node)}`"
        @click="open(node)"
        @keydown="onKey($event, node)"
      >
        <circle
          :cx="node.x"
          :cy="node.y"
          :r="isCurrent(node) ? 8 : 6"
          :fill="
            node.save || node.snapshot?.kind === 'branch'
              ? 'var(--r-color-bg)'
              : LANE_COLORS[node.lane % LANE_COLORS.length]
          "
          :stroke="LANE_COLORS[node.lane % LANE_COLORS.length]"
          stroke-width="2"
        />
        <circle
          v-if="node.snapshot?.is_pinned"
          :cx="node.x + 7"
          :cy="node.y - 7"
          r="3"
          fill="var(--r-color-brand-accent)"
        />
        <text :x="textX" :y="node.y - 2" class="r-channel-timeline__headline">
          {{ headline(node) }}
        </text>
        <text :x="textX" :y="node.y + 14" class="r-channel-timeline__detail">
          {{ detail(node) }}
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.r-channel-timeline {
  overflow-x: auto;
  padding: var(--r-space-3);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
}
.r-channel-timeline svg {
  display: block;
}
.r-channel-timeline__node {
  cursor: pointer;
  outline: none;
}
.r-channel-timeline__headline {
  fill: var(--r-color-fg);
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
}
.r-channel-timeline__detail {
  fill: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}
html[data-input="key"]
  .r-channel-timeline__node:focus-visible
  circle:first-child,
html[data-input="pad"]
  .r-channel-timeline__node:focus-visible
  circle:first-child {
  stroke: var(--r-color-fg);
  stroke-width: 3;
}
</style>
