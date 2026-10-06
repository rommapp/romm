<script setup lang="ts">
import { RBtn, RSliderBtnGroup } from "@v2/lib";
import type { SliderBtnGroupItem } from "@v2/lib";
import { isAxiosError } from "axios";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type {
  ChannelSchema,
  DetailedRomSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import snapshotApi, { type SnapshotManifest } from "@/services/api/snapshot";
import storeConfig from "@/stores/config";
import { getSupportedEJSCores } from "@/utils";
import ChannelFan from "@/v2/components/GameDetails/SaveChannels/ChannelFan.vue";
import ChannelLabelDialog, {
  type ChannelLabelSubmit,
  type StartOption,
} from "@/v2/components/GameDetails/SaveChannels/ChannelLabelDialog.vue";
import ChannelTile from "@/v2/components/GameDetails/SaveChannels/ChannelTile.vue";
import ChannelTimeline from "@/v2/components/GameDetails/SaveChannels/ChannelTimeline.vue";
import SnapshotViewer, {
  type ViewerTarget,
} from "@/v2/components/GameDetails/SaveChannels/SnapshotViewer.vue";
import { useCanPlay } from "@/v2/composables/useCanPlay";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFetchState } from "@/v2/composables/useFetchState";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";
import { playerPath } from "@/v2/utils/playerPath";
import { isHardcoreRefusal } from "@/v2/utils/saveSync/snapshotSession";
import {
  saveOverManifest,
  copySaveManifest,
  saveOverTargets,
  forkManifest,
  isBackup,
  restoreManifest,
  withoutStateManifest,
} from "@/v2/utils/snapshots";

type View = "tiles" | "timeline";

const HISTORY_PAGE = 20;

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    rom: DetailedRomSchema;
    channels: ChannelSchema[];
    /** The viewer's own saves on this ROM, legacy-linked ones and backups. */
    saves: SaveSchema[];
    /** Own channels get the New channel button and the view toggle. */
    own?: boolean;
  }>(),
  { own: false },
);

const emit = defineEmits<{
  download: [path: string, name: string];
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { refetchRom } = useRomSync();
const router = useRouter();
const configStore = storeConfig();

const view = ref<View>("tiles");
const viewItems = computed<SliderBtnGroupItem<View>[]>(() => [
  {
    id: "tiles",
    icon: "mdi-view-grid-outline",
    ariaLabel: t("channels.view-tiles"),
    title: t("channels.view-tiles"),
  },
  {
    id: "timeline",
    icon: "mdi-source-branch",
    ariaLabel: t("channels.view-timeline"),
    title: t("channels.view-timeline"),
  },
]);

/** Saves an older client filed under a channel by slot, with no snapshot. */
const legacySaves = computed(() => {
  const held = new Set(props.rom.snapshot_save_ids);
  const byChannel: Record<string, SaveSchema[]> = {};
  for (const save of props.saves) {
    if (!save.channel_id || !save.slot || held.has(save.id)) continue;
    (byChannel[save.channel_id] ??= []).push(save);
  }
  for (const list of Object.values(byChannel)) {
    list.sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  }
  return byChannel;
});
const backups = computed(() => props.saves.filter(isBackup));

const histories = reactive<Record<string, SnapshotSchema[] | null>>({});
const hasMore = reactive<Record<string, boolean>>({});
const loadingMore = ref<string | null>(null);

async function loadHistory(channel: ChannelSchema, more = false) {
  const loaded = histories[channel.id] ?? [];
  if (!more) histories[channel.id] = null;
  else loadingMore.value = channel.id;
  try {
    const { data } = await snapshotApi.getChannelHistory({
      channelId: channel.id,
      limit: HISTORY_PAGE,
      cursor: more ? loaded[loaded.length - 1]?.id : undefined,
    });
    histories[channel.id] = more ? [...loaded, ...data] : data;
    hasMore[channel.id] = data.length === HISTORY_PAGE;
  } catch (error) {
    histories[channel.id] = loaded;
    snackbar.error(t("channels.cant-load", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  } finally {
    loadingMore.value = null;
  }
}

const expandedId = ref<string | null>(null);
const expanded = computed(
  () => props.channels.find((c) => c.id === expandedId.value) ?? null,
);

function toggle(channel: ChannelSchema) {
  expandedId.value = expandedId.value === channel.id ? null : channel.id;
  if (expandedId.value && channel.current) void loadHistory(channel);
}

watch(view, (next) => {
  if (next !== "timeline") return;
  for (const channel of props.channels) {
    if (channel.current && histories[channel.id] === undefined) {
      void loadHistory(channel);
    }
  }
});

async function refresh() {
  await refetchRom(props.rom.id);
  const shown =
    view.value === "timeline"
      ? props.channels
      : expanded.value
        ? [expanded.value]
        : [];
  await Promise.all(shown.filter((c) => c.current).map((c) => loadHistory(c)));
}

const viewerTarget = ref<ViewerTarget | null>(null);
const busy = ref(false);

function openSnapshot(channel: ChannelSchema, snapshot: SnapshotSchema) {
  viewerTarget.value = { kind: "snapshot", channel, snapshot };
}
function openSave(channel: ChannelSchema, save: SaveSchema) {
  viewerTarget.value = { kind: "save", channel, save };
}
const viewerSaveOverTargets = computed(() =>
  viewerTarget.value
    ? saveOverTargets(props.channels, viewerTarget.value.channel)
    : [],
);

const { canPlayEJS } = useCanPlay(() => props.rom);
const playableCores = computed(() =>
  canPlayEJS.value
    ? [
        ...getSupportedEJSCores(
          props.rom.platform_slug,
          configStore.config.EJS_NETPLAY_ENABLED,
        ),
      ]
    : [],
);

function play(stateId: number | null) {
  const target = viewerTarget.value;
  if (target?.kind !== "snapshot") return;
  void router.push({
    path: playerPath(props.rom.id, "ejs"),
    query: {
      snapshot: String(target.snapshot.id),
      ...(stateId != null ? { state: String(stateId) } : {}),
    },
  });
}

/**
 * Pushes `manifest`, asking first when it would replace a hardcore save.
 * A push that lost a race to another device refreshes instead of retrying.
 */
async function push(manifest: SnapshotManifest | null, done: string) {
  if (!manifest || busy.value) return;
  busy.value = true;
  try {
    try {
      await snapshotApi.pushSnapshot({ manifest });
    } catch (error) {
      if (!isAxiosError(error) || error.response?.status !== 409) throw error;
      if (!isHardcoreRefusal(error)) {
        snackbar.warning(t("channels.stale"), { icon: "mdi-sync-alert" });
        await refresh();
        return;
      }
      const ok = await confirm({
        title: t("channels.hardcore-title"),
        body: t("channels.hardcore-body"),
        confirmText: t("channels.hardcore-confirm"),
        tone: "warning",
      });
      if (!ok) return;
      await snapshotApi.pushSnapshot({
        manifest: { ...manifest, approve_hardcore_downgrade: true },
      });
    }
    snackbar.success(done, { icon: "mdi-check-bold" });
    viewerTarget.value = null;
    await refresh();
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  } finally {
    busy.value = false;
  }
}

function restore() {
  const target = viewerTarget.value;
  if (target?.kind !== "snapshot") return;
  void push(
    restoreManifest(target.snapshot, target.channel),
    t("channels.restored"),
  );
}

function removeState(core: string, slot: string) {
  const target = viewerTarget.value;
  if (target?.kind !== "snapshot") return;
  void push(
    withoutStateManifest(target.snapshot, target.channel, core, slot),
    t("channels.state-removed"),
  );
}

function saveOver(other: ChannelSchema) {
  const target = viewerTarget.value;
  if (target?.kind !== "snapshot") return;
  void push(
    saveOverManifest(target.snapshot, other),
    t("channels.saved-over", { label: other.label }),
  );
}

function makeSnapshot() {
  const target = viewerTarget.value;
  if (target?.kind !== "save") return;
  void push(
    copySaveManifest(target.save, target.channel),
    t("channels.made-snapshot"),
  );
}

async function togglePin() {
  const target = viewerTarget.value;
  if (target?.kind !== "snapshot" || busy.value) return;
  busy.value = true;
  const isPinned = !target.snapshot.is_pinned;
  try {
    const { data } = await snapshotApi.setSnapshotPinned({
      id: target.snapshot.id,
      isPinned,
    });
    viewerTarget.value = { ...target, snapshot: data };
    const list = histories[target.channel.id];
    if (list) {
      histories[target.channel.id] = list.map((s) =>
        s.id === data.id ? data : s,
      );
    }
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  } finally {
    busy.value = false;
  }
}

type LabelMode =
  | { kind: "new" }
  | { kind: "rename"; channel: ChannelSchema }
  | { kind: "fork"; snapshot: SnapshotSchema; romFileId: number };
const labelMode = ref<LabelMode | null>(null);

const labelDialog = computed(() => {
  const mode = labelMode.value;
  if (mode?.kind === "rename") {
    return {
      title: t("channels.rename-title"),
      confirmText: t("channels.rename"),
      initialLabel: mode.channel.label,
    };
  }
  if (mode?.kind === "fork") {
    return {
      title: t("channels.fork-title"),
      confirmText: t("channels.fork"),
      initialLabel: "",
    };
  }
  return {
    title: t("channels.new-title"),
    confirmText: t("channels.create"),
    initialLabel: "",
  };
});

const startOptions = computed<StartOption[]>(() =>
  labelMode.value?.kind === "new"
    ? [
        ...backups.value.map((save) => ({
          saveId: save.id,
          title: save.file_name,
        })),
        { saveId: null, title: t("channels.start-empty") },
      ]
    : [],
);

/** The ROM's file a new channel keys to: the one existing channels use, else the server's pick. */
const defaultRomFileId = computed(
  () =>
    props.channels.find((c) => c.is_own && c.rom_file_id != null)
      ?.rom_file_id ??
    props.rom.channel_file_id ??
    null,
);

const { state: detached, execute: loadDetached } = useFetchState(
  (platformId: number) =>
    snapshotApi.getDetachedChannels({ platformId }).then(({ data }) => data),
  [] as ChannelSchema[],
  { immediate: false },
);
watch(
  () => (props.own ? props.rom.platform_id : null),
  (platformId) => {
    if (platformId != null) void loadDetached(platformId);
  },
  { immediate: true },
);

const attaching = ref<string | null>(null);

async function attach(channel: ChannelSchema) {
  const romFileId = defaultRomFileId.value;
  if (romFileId == null || attaching.value) return;
  attaching.value = channel.id;
  try {
    await snapshotApi.attachChannel({ id: channel.id, romFileId });
    snackbar.success(t("channels.attached"), { icon: "mdi-check-bold" });
    await refetchRom(props.rom.id);
    await loadDetached(props.rom.platform_id);
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  } finally {
    attaching.value = null;
  }
}

function startFork() {
  const target = viewerTarget.value;
  const romFileId = target?.channel.rom_file_id ?? defaultRomFileId.value;
  if (target?.kind !== "snapshot" || romFileId == null) return;
  labelMode.value = { kind: "fork", snapshot: target.snapshot, romFileId };
}

async function submitLabel({ label, startFrom }: ChannelLabelSubmit) {
  const mode = labelMode.value;
  if (!mode || busy.value) return;
  if (mode.kind === "fork") {
    labelMode.value = null;
    await push(
      forkManifest(mode.snapshot, mode.romFileId, label),
      t("channels.forked"),
    );
    return;
  }
  busy.value = true;
  try {
    if (mode.kind === "rename") {
      await snapshotApi.updateChannel({ id: mode.channel.id, label });
      snackbar.success(t("channels.renamed"), { icon: "mdi-check-bold" });
      labelMode.value = null;
      await refresh();
      return;
    }
    const romFileId = defaultRomFileId.value;
    if (romFileId == null) return;
    const { data: created } = await snapshotApi.createChannel({
      romFileId,
      label,
    });
    labelMode.value = null;
    if (startFrom != null) {
      busy.value = false;
      await push(
        copySaveManifest({ id: startFrom }, created),
        t("channels.created"),
      );
      return;
    }
    snackbar.success(t("channels.created"), { icon: "mdi-check-bold" });
    await refresh();
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  } finally {
    busy.value = false;
  }
}

async function toggleShare(channel: ChannelSchema) {
  const isPublic = !channel.is_public;
  if (isPublic) {
    const ok = await confirm({
      title: t("channels.share-title"),
      body: t("channels.share-body"),
      confirmText: t("channels.share"),
      tone: "warning",
    });
    if (!ok) return;
  }
  try {
    await snapshotApi.updateChannel({ id: channel.id, isPublic });
    snackbar.success(
      isPublic ? t("channels.shared-done") : t("channels.unshared"),
      {
        icon: "mdi-check-bold",
      },
    );
    await refresh();
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  }
}

async function deleteChannel(channel: ChannelSchema) {
  const pinned = (histories[channel.id] ?? []).filter(
    (s) => s.is_pinned,
  ).length;
  const ok = await confirm({
    title: t("channels.delete-title", { label: channel.label }),
    body: t("channels.delete-body", {
      pinned,
      legacy: legacySaves.value[channel.id]?.length ?? 0,
    }),
    confirmText: t("channels.delete"),
    tone: "danger",
    requireTyped: channel.label,
  });
  if (!ok) return;
  try {
    await snapshotApi.deleteChannel({ id: channel.id });
    expandedId.value = null;
    snackbar.success(t("channels.deleted"), { icon: "mdi-check-bold" });
    await refresh();
  } catch (error) {
    snackbar.error(t("channels.failed", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  }
}
</script>

<template>
  <div class="r-channels" v-bind="$attrs">
    <header class="r-channels__head">
      <h4 class="r-channels__title">{{ t("channels.section") }}</h4>
      <div class="r-channels__tools">
        <RSliderBtnGroup
          v-model="view"
          :items="viewItems"
          :aria-label="t('channels.view-label')"
        />
        <RBtn
          v-if="own"
          variant="outlined"
          size="small"
          prepend-icon="mdi-plus"
          :disabled="defaultRomFileId == null"
          @click="labelMode = { kind: 'new' }"
        >
          {{ t("channels.new") }}
        </RBtn>
      </div>
    </header>

    <p v-if="channels.length === 0" class="r-channels__empty">
      {{ t("channels.none") }}
    </p>
    <div v-else-if="view === 'tiles'" class="r-channels__tiles">
      <template v-for="channel in channels" :key="channel.id">
        <ChannelFan
          v-if="expandedId === channel.id"
          :channel="channel"
          :history="channel.current ? (histories[channel.id] ?? null) : []"
          :legacy-saves="legacySaves[channel.id] ?? []"
          :has-more="!!hasMore[channel.id]"
          :loading-more="loadingMore === channel.id"
          @collapse="expandedId = null"
          @open-snapshot="openSnapshot(channel, $event)"
          @open-save="openSave(channel, $event)"
          @rename="labelMode = { kind: 'rename', channel }"
          @toggle-share="toggleShare(channel)"
          @delete="deleteChannel(channel)"
          @load-more="loadHistory(channel, true)"
        />
        <ChannelTile
          v-else
          :channel="channel"
          :legacy-saves="legacySaves[channel.id] ?? []"
          :data-focus-key="channel.id"
          @open="toggle(channel)"
        />
      </template>
    </div>
    <ChannelTimeline
      v-else
      :channels="channels"
      :histories="histories"
      :legacy-saves="legacySaves"
      @open-snapshot="openSnapshot"
      @open-save="openSave"
    />

    <section v-if="own && detached.length > 0" class="r-channels__detached">
      <h5 class="r-channels__detached-title">{{ t("channels.detached") }}</h5>
      <p class="r-channels__empty">{{ t("channels.detached-hint") }}</p>
      <div
        v-for="channel in detached"
        :key="channel.id"
        class="r-channels__detached-row"
      >
        <span class="r-channels__detached-label">{{ channel.label }}</span>
        <span class="r-channels__detached-count">{{
          t("channels.snapshots-n", channel.snapshot_count, {
            named: { n: channel.snapshot_count },
          })
        }}</span>
        <RBtn
          variant="outlined"
          size="small"
          prepend-icon="mdi-link-variant"
          :loading="attaching === channel.id"
          :disabled="attaching !== null || defaultRomFileId == null"
          @click="attach(channel)"
        >
          {{ t("channels.attach") }}
        </RBtn>
      </div>
    </section>

    <SnapshotViewer
      :target="viewerTarget"
      :save-over-targets="viewerSaveOverTargets"
      :busy="busy"
      :playable-cores="playableCores"
      @close="viewerTarget = null"
      @play="play"
      @restore="restore"
      @remove-state="removeState"
      @fork="startFork"
      @save-over="saveOver"
      @toggle-pin="togglePin"
      @make-snapshot="makeSnapshot"
      @download="(path, name) => emit('download', path, name)"
    />

    <ChannelLabelDialog
      :model-value="labelMode !== null"
      :title="labelDialog.title"
      :confirm-text="labelDialog.confirmText"
      :initial-label="labelDialog.initialLabel"
      :start-options="startOptions"
      :busy="busy"
      @update:model-value="!$event && (labelMode = null)"
      @submit="submitLabel"
    />
  </div>
</template>

<style scoped>
.r-channels {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
.r-channels__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
}
.r-channels__title {
  margin: 0;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}
.r-channels__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-2);
}
.r-channels__empty {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}
.r-channels__detached {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}
.r-channels__detached-title {
  margin: 0;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
}
.r-channels__detached-row {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-2) var(--r-space-3);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-channels__detached-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-weight: var(--r-font-weight-semibold);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-channels__detached-count {
  flex: none;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}
.r-channels__tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--r-space-4);
}
</style>
