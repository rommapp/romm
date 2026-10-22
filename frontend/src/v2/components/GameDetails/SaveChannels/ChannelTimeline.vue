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

const CHANNEL_COLORS = [
  "var(--r-color-brand-primary)",
  "var(--r-color-brand-accent)",
  "var(--r-color-success)",
  "var(--r-color-info)",
];
const LANE_W = 34;
const ROW_H = 46;
const LEFT = 30;
const ARC_REACH = LANE_W * 0.7;
const TOP = 22;

interface Node {
  key: string;
  lane: number;
  color: string;
  channel: ChannelSchema;
  snapshot: SnapshotSchema | null;
  save: SaveSchema | null;
  at: number;
  x: number;
  y: number;
}

const colorByChannel = computed(
  () =>
    new Map(
      [...props.channels]
        .sort(
          (a, b) =>
            Date.parse(a.created_at) - Date.parse(b.created_at) ||
            a.id.localeCompare(b.id),
        )
        .map((channel, age) => [
          channel.id,
          CHANNEL_COLORS[age % CHANNEL_COLORS.length]!,
        ]),
    ),
);

const nodes = computed<Node[]>(() => {
  const unplaced = props.channels.flatMap((channel, lane) => [
    ...(props.histories[channel.id] ?? []).map((snapshot) => ({
      key: `s-${snapshot.id}`,
      lane,
      color: colorByChannel.value.get(channel.id)!,
      channel,
      snapshot,
      save: null,
      at: Date.parse(snapshot.created_at),
    })),
    ...(props.legacySaves[channel.id] ?? []).map((save) => ({
      key: `l-${save.id}`,
      lane,
      color: colorByChannel.value.get(channel.id)!,
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

const parentIds = computed(
  () => new Set(nodes.value.map((n) => n.snapshot?.parent_snapshot_id)),
);

function isCurrent(node: Node): boolean {
  return node.snapshot?.id === node.channel.current_snapshot_id;
}

function isAbandoned(node: Node): boolean {
  return (
    node.snapshot?.kind === "channel" &&
    !isCurrent(node) &&
    !parentIds.value.has(node.snapshot.id)
  );
}

function skipsOver(parent: Node, node: Node): boolean {
  return (
    parent.lane === node.lane &&
    nodes.value.some(
      (n) => n.lane === node.lane && n.y > node.y && n.y < parent.y,
    )
  );
}

function edgePath(parent: Node, node: Node): string {
  if (skipsOver(parent, node)) {
    const arcX = node.x - ARC_REACH;
    return `M${parent.x},${parent.y} C${arcX},${parent.y} ${arcX},${node.y} ${node.x},${node.y}`;
  }
  const midY = (parent.y + node.y) / 2;
  return `M${parent.x},${parent.y} C${parent.x},${midY} ${node.x},${midY} ${node.x},${node.y}`;
}

const edges = computed(() =>
  nodes.value.flatMap((node) => {
    const parentId = node.snapshot?.parent_snapshot_id;
    const parent = parentId ? bySnapshotId.value.get(parentId) : undefined;
    if (!parent || !node.snapshot) return [];
    return [
      {
        key: `${parent.key}-${node.key}`,
        d: edgePath(parent, node),
        color: node.color,
        branch: node.snapshot.kind === "branch",
        abandoned: isAbandoned(node),
      },
    ];
  }),
);

function headline(node: Node): string {
  const parts = [node.channel.label];
  if (node.snapshot?.kind === "branch") parts.push(t("channels.branch"));
  if (node.snapshot?.pin_count) parts.push(t("channels.pinned"));
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
      <path
        v-for="edge in edges"
        :key="edge.key"
        :d="edge.d"
        fill="none"
        :stroke="edge.abandoned ? 'var(--r-color-fg-muted)' : edge.color"
        stroke-width="2"
        :stroke-dasharray="edge.branch ? '4 4' : undefined"
        :stroke-opacity="edge.branch || edge.abandoned ? 0.6 : 1"
      />
      <g
        v-for="node in nodes"
        :key="node.key"
        class="r-channel-timeline__node"
        :class="{ 'r-channel-timeline__node--abandoned': isAbandoned(node) }"
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
              : node.color
          "
          :stroke="node.color"
          stroke-width="2"
        />
        <circle
          v-if="node.snapshot?.pin_count"
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
.r-channel-timeline__node--abandoned {
  opacity: 0.5;
}
.r-channel-timeline__node--abandoned circle:first-child {
  fill: var(--r-color-fg-muted);
  stroke: var(--r-color-fg-muted);
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
