<script setup lang="ts">
import { RBtn, RChip, RDrawer, RIcon, RImg, RMenu, RMenuItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type {
  ChannelSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import { formatRelativeDate } from "@/utils";
import { useDeviceLabel } from "@/v2/composables/useDeviceLabel";
import { emulatorKey } from "@/v2/utils/assets";
import { AUTO_STATE_SLOT, snapshotBadges } from "@/v2/utils/snapshots";

/** What the drawer shows: a snapshot, or a save an older client filed without one. */
export type ViewerTarget =
  | { kind: "snapshot"; channel: ChannelSchema; snapshot: SnapshotSchema }
  | { kind: "save"; channel: ChannelSchema; save: SaveSchema };

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    target: ViewerTarget | null;
    /** The user's other channels on the same file. */
    saveOverTargets?: ChannelSchema[];
    /** The in-browser player's cores for this ROM; empty when it cannot run it. */
    playableCores?: string[];
    busy?: boolean;
  }>(),
  { saveOverTargets: () => [], playableCores: () => [], busy: false },
);

const emit = defineEmits<{
  close: [];
  /** Boot the snapshot, from one of its states when given. */
  play: [stateId: number | null];
  restore: [];
  removeState: [core: string, slot: string];
  fork: [];
  saveOver: [target: ChannelSchema];
  togglePin: [];
  makeSnapshot: [];
  download: [path: string, name: string];
}>();

const { t } = useI18n();
const deviceLabel = useDeviceLabel();

const snapshot = computed(() =>
  props.target?.kind === "snapshot" ? props.target.snapshot : null,
);
const save = computed(() =>
  props.target?.kind === "save" ? props.target.save : null,
);
const channel = computed(() => props.target?.channel ?? null);
const own = computed(() => !!channel.value?.is_own);
const isCurrent = computed(
  () =>
    !!snapshot.value &&
    snapshot.value.id === channel.value?.current_snapshot_id,
);
const canWrite = computed(() => own.value || !!channel.value?.is_public);
const badges = computed(() =>
  snapshot.value && channel.value
    ? snapshotBadges(snapshot.value, channel.value, t)
    : [],
);

const title = computed(() => {
  if (snapshot.value) {
    return `${formatRelativeDate(snapshot.value.created_at)} · #${snapshot.value.id}`;
  }
  return save.value ? formatRelativeDate(save.value.updated_at) : "";
});
const heroSrc = computed(
  () =>
    snapshot.value?.thumbnail?.download_path ??
    save.value?.screenshot?.download_path,
);
const details = computed<[string, string, boolean?][]>(() => {
  const rows: [string, string, boolean?][] = [
    [t("channels.channel"), channel.value?.label ?? ""],
  ];
  if (snapshot.value) {
    rows.push(
      [t("channels.device"), deviceLabel(snapshot.value.device)],
      [
        t("channels.parent"),
        snapshot.value.parent_snapshot_id
          ? `#${snapshot.value.parent_snapshot_id}`
          : "-",
      ],
    );
    if (snapshot.value.save) {
      rows.push([t("channels.file"), snapshot.value.save.file_name, true]);
    }
  } else if (save.value) {
    rows.push([t("channels.file"), save.value.file_name, true]);
  }
  return rows;
});
/** Auto first, then numbered slots by number, then any other name. */
function slotOrder(a: string, b: string): number {
  const rank = (slot: string) =>
    slot === AUTO_STATE_SLOT
      ? -1
      : /^\d+$/.test(slot)
        ? Number(slot)
        : Infinity;
  return rank(a) - rank(b) || a.localeCompare(b);
}

const cores = computed(() =>
  Object.entries(snapshot.value?.states ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(
      ([core, slots]) =>
        [
          core,
          Object.entries(slots).sort(([a], [b]) => slotOrder(a, b)),
        ] as const,
    ),
);

function isPlayableCore(core: string): boolean {
  return (
    own.value &&
    props.playableCores.some((c) => emulatorKey(c) === emulatorKey(core))
  );
}

/** The snapshot boots in the browser from a state a core there runs, or from its native save. */
const canPlay = computed(() => {
  if (!own.value || !snapshot.value || props.playableCores.length === 0) {
    return false;
  }
  return (
    snapshot.value.save?.format !== "neutral" ||
    Object.keys(snapshot.value.states).some(isPlayableCore)
  );
});

function slotLabel(slot: string): string {
  return slot === AUTO_STATE_SLOT
    ? t("channels.slot-auto")
    : t("channels.slot-n", { slot });
}

function downloadSave() {
  const file = snapshot.value?.save ?? save.value;
  if (file) emit("download", file.download_path, file.file_name);
}

interface Action {
  key: string;
  label: string;
  icon: string;
  /** Changes the channel, so it waits out an in-flight push. */
  writes: boolean;
  run: () => void;
}

/** Every action the target offers, most likely first: the first is the footer's button, the rest its menu. */
const actions = computed<Action[]>(() => {
  const list: Action[] = [];
  const download: Action = {
    key: "download",
    label: t("channels.download"),
    icon: "mdi-download-outline",
    writes: false,
    run: downloadSave,
  };
  if (save.value) {
    if (own.value) {
      list.push({
        key: "make-snapshot",
        label: t("channels.make-snapshot"),
        icon: "mdi-layers-plus",
        writes: true,
        run: () => emit("makeSnapshot"),
      });
    }
    list.push(download);
    return list;
  }
  if (!snapshot.value) return list;
  if (canPlay.value) {
    list.push({
      key: "play",
      label: t("channels.play-from-here"),
      icon: "mdi-play",
      writes: false,
      run: () => emit("play", null),
    });
  }
  if (!isCurrent.value && canWrite.value) {
    list.push({
      key: "restore",
      label: t("channels.restore"),
      icon: "mdi-restore",
      writes: true,
      run: () => emit("restore"),
    });
  }
  if (snapshot.value.save) list.push(download);
  list.push({
    key: "fork",
    label: t("channels.fork"),
    icon: "mdi-source-fork",
    writes: true,
    run: () => emit("fork"),
  });
  for (const other of props.saveOverTargets) {
    list.push({
      key: `save-over-${other.id}`,
      label: t("channels.save-over-named", { label: other.label }),
      icon: "mdi-source-merge",
      writes: true,
      run: () => emit("saveOver", other),
    });
  }
  return list;
});
const primary = computed(() => actions.value[0] ?? null);
const overflow = computed(() => actions.value.slice(1));
</script>

<template>
  <RDrawer
    :model-value="target !== null"
    icon="mdi-content-save-outline"
    :width="440"
    v-bind="$attrs"
    @update:model-value="!$event && emit('close')"
  >
    <template #header>
      <span>{{ title }}</span>
    </template>

    <div v-if="target" class="r-snapshot-viewer">
      <RImg v-if="heroSrc" class="r-snapshot-viewer__hero" :src="heroSrc" />

      <div class="r-snapshot-viewer__badges">
        <RChip
          v-for="badge in badges"
          :key="badge.label"
          size="small"
          :color="badge.color"
          :variant="badge.outlined ? 'outlined' : 'translucent'"
        >
          {{ badge.label }}
        </RChip>
        <RChip v-if="save" size="small" variant="outlined">
          {{ t("channels.legacy-save") }}
        </RChip>
      </div>

      <dl class="r-snapshot-viewer__details">
        <template v-for="[label, value, mono] in details" :key="label">
          <dt>{{ label }}</dt>
          <dd :class="{ 'r-snapshot-viewer__mono': mono }">{{ value }}</dd>
        </template>
      </dl>

      <section v-if="snapshot" class="r-snapshot-viewer__bank">
        <h3 class="r-snapshot-viewer__heading">
          {{ t("channels.states-title") }}
        </h3>
        <p v-if="cores.length === 0" class="r-snapshot-viewer__empty">
          {{
            snapshot.is_hardcore
              ? t("channels.hardcore-no-states")
              : t("channels.no-states")
          }}
        </p>
        <div
          v-for="[core, slots] in cores"
          :key="core"
          class="r-snapshot-viewer__core"
        >
          <span class="r-snapshot-viewer__core-name">{{ core }}</span>
          <div class="r-snapshot-viewer__slots">
            <figure
              v-for="[slot, state] in slots"
              :key="slot"
              class="r-snapshot-viewer__slot"
            >
              <RImg
                v-if="state.screenshot"
                class="r-snapshot-viewer__slot-thumb"
                :src="state.screenshot.download_path"
              />
              <span
                v-else
                class="r-snapshot-viewer__slot-thumb r-snapshot-viewer__slot-thumb--empty"
              >
                <RIcon icon="mdi-camera-outline" size="20" />
              </span>
              <figcaption class="r-snapshot-viewer__slot-caption">
                <span class="r-snapshot-viewer__slot-name">{{
                  slotLabel(slot)
                }}</span>
                <span class="r-snapshot-viewer__mono">{{
                  state.content_hash?.slice(0, 8)
                }}</span>
              </figcaption>
              <RBtn
                v-if="isPlayableCore(core)"
                class="r-snapshot-viewer__slot-play"
                icon="mdi-play"
                variant="flat"
                size="x-small"
                :tooltip="t('channels.play-state')"
                :aria-label="
                  t('channels.play-state-named', {
                    core,
                    slot: slotLabel(slot),
                  })
                "
                @click="emit('play', state.id)"
              />
              <RBtn
                v-if="canWrite"
                class="r-snapshot-viewer__slot-remove"
                icon="mdi-close"
                variant="flat"
                size="x-small"
                :disabled="busy"
                :tooltip="
                  isCurrent
                    ? t('channels.remove-state')
                    : t('channels.restore-without')
                "
                :aria-label="
                  t('channels.remove-state-named', {
                    core,
                    slot: slotLabel(slot),
                  })
                "
                @click="emit('removeState', core, slot)"
              />
            </figure>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <div v-if="target" class="r-snapshot-viewer__actions">
        <RBtn
          v-if="primary"
          class="r-snapshot-viewer__primary"
          :variant="primary.writes ? 'flat' : 'outlined'"
          :color="primary.writes ? 'primary' : undefined"
          :prepend-icon="primary.icon"
          :loading="primary.writes && busy"
          :disabled="primary.writes && busy"
          @click="primary.run"
        >
          {{ primary.label }}
        </RBtn>
        <div class="r-snapshot-viewer__tools">
          <RBtn
            v-if="snapshot && canWrite"
            :icon="
              snapshot.is_pinned ? 'mdi-pin-off-outline' : 'mdi-pin-outline'
            "
            variant="text"
            :aria-label="
              snapshot.is_pinned ? t('channels.unpin') : t('channels.pin')
            "
            :tooltip="
              snapshot.is_pinned ? t('channels.unpin') : t('channels.pin')
            "
            :aria-pressed="snapshot.is_pinned"
            :disabled="busy"
            @click="emit('togglePin')"
          />
          <RMenu v-if="overflow.length > 0" location="top end" :offset="6">
            <template #activator="{ props: activatorProps }">
              <RBtn
                v-bind="activatorProps"
                icon="mdi-dots-vertical"
                variant="text"
                :aria-label="t('rom.more-actions')"
                :tooltip="t('rom.more-actions')"
              />
            </template>
            <RMenuItem
              v-for="action in overflow"
              :key="action.key"
              :label="action.label"
              :icon="action.icon"
              :disabled="action.writes && busy"
              @click="action.run"
            />
          </RMenu>
        </div>
      </div>
    </template>
  </RDrawer>
</template>

<style scoped>
.r-snapshot-viewer {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}
.r-snapshot-viewer__hero {
  width: 100%;
  overflow: hidden;
  border-radius: var(--r-radius-lg);
  background: var(--r-color-bg-elevated);
}
.r-snapshot-viewer__hero :deep(img),
.r-snapshot-viewer__slot-thumb :deep(img) {
  image-rendering: pixelated;
}
.r-snapshot-viewer__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-1);
}
.r-snapshot-viewer__details {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--r-space-1) var(--r-space-3);
  margin: 0;
  font-size: var(--r-font-size-sm);
}
.r-snapshot-viewer__details dt {
  color: var(--r-color-fg-muted);
}
.r-snapshot-viewer__details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.r-snapshot-viewer__mono {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
.r-snapshot-viewer__bank {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
.r-snapshot-viewer__heading {
  margin: 0;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}
.r-snapshot-viewer__empty {
  margin: 0;
  color: var(--r-color-fg-muted);
}
.r-snapshot-viewer__core {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}
.r-snapshot-viewer__core-name {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}
.r-snapshot-viewer__slots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--r-space-3);
}
.r-snapshot-viewer__slot {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
  margin: 0;
}
.r-snapshot-viewer__slot-thumb {
  width: 100%;
  overflow: hidden;
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
.r-snapshot-viewer__slot-thumb--empty {
  display: grid;
  place-items: center;
  aspect-ratio: 3 / 2;
  color: var(--r-color-fg-muted);
}
.r-snapshot-viewer__slot-caption {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--r-space-2);
  min-width: 0;
  font-size: var(--r-font-size-sm);
}
.r-snapshot-viewer__slot-name {
  font-weight: var(--r-font-weight-semibold);
}
.r-snapshot-viewer__slot-remove {
  position: absolute;
  top: var(--r-space-1);
  right: var(--r-space-1);
}
.r-snapshot-viewer__slot-play {
  position: absolute;
  top: var(--r-space-1);
  left: var(--r-space-1);
}
.r-snapshot-viewer__actions {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  width: 100%;
}
.r-snapshot-viewer__tools {
  display: flex;
  align-items: center;
  gap: var(--r-space-1);
  margin-left: auto;
}
</style>
