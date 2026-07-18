<script setup lang="ts">
// EditRomDialog — v2 chrome around the ROM-edit form.
//
// Scope: identity (name / filename / summary), cover artwork, and the
// metadata override / raw provider tabs. Manual + soundtrack +
// screenshots are intentionally absent — those flows now live in the
// GameDetails Media tab (`v2/components/GameDetails/MediaTab.vue`).
// Pulling them out of the edit dialog kept it focused on "data that
// describes this ROM" and freed the form column from the icon-button
// row that fought visually with the field stack.
//
// Layout: a hero row (cover + name/filename/summary) at the top, and a
// tabbed editing surface below — "Details" and "Metadata IDs" are
// always present; one tab per metadata provider with a populated ID is
// appended dynamically (and disappears once the rom is unmatched from
// that provider). Cover actions, AdditionalDetails and MetadataIdSection
// remain deep domain composites pulled from the EditRom feature folder.
import { RBtn, RDialog, RIcon, RTabNav, RTextField } from "@v2/lib";
import type { RTabNavItem } from "@v2/lib/primitives/RTabNav/types";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AdditionalDetails from "@/v2/components/EditRom/AdditionalDetails.vue";
import MetadataIdSection from "@/v2/components/EditRom/MetadataIdSection.vue";
import RawMetadataPanel from "@/v2/components/EditRom/RawMetadataPanel.vue";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { getMissingCoverImage } from "@/v2/utils/covers";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { lgAndUp } = useBreakpoint();
const heartbeat = storeHeartbeat();
const route = useRoute();
const show = ref(false);
// `UpdateRom = SimpleRom & {...}` but we keep a DetailedRom-compatible
// shape internally so the per-provider raw-metadata panels can read
// their payloads. Widen at edit/emit boundaries.
type EditableRom = DetailedRom & UpdateRom;
const rom = ref<EditableRom | null>(null);
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const coverFileInput = ref<HTMLInputElement | null>(null);
// In-flight flag for the PUT — drives the footer button's spinner so
// the user sees the action is running. v1 leaned on a global
// `showLoadingDialog` event for the same feedback, but v2 has no
// listener for it (intentionally — inline `:loading` on the control
// itself is the v2 pattern, see CLAUDE.md §VI.B), so the emit was a
// no-op and the dialog appeared frozen during slow uploads / SGDB
// fetches.
const saving = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const openHandler = async (romToEdit: SimpleRom) => {
  show.value = true;
  // Show the simple rom immediately so the dialog mounts; fetch the
  // detailed version in the background so provider metadata panels
  // have real data to render.
  rom.value = romToEdit as EditableRom;
  removeCover.value = false;
  imagePreviewUrl.value = "";
  activeTab.value = "details";
  try {
    const { data } = await romApi.getRom({ romId: romToEdit.id });
    if (show.value) rom.value = data as EditableRom;
  } catch (error) {
    console.error("Failed to fetch detailed rom", error);
  }
};
emitter?.on("showEditRomDialog", openHandler);

const urlCoverHandler = (url_cover: string) => setUrlCover(url_cover);
emitter?.on("updateUrlCover", urlCoverHandler);

onBeforeUnmount(() => {
  emitter?.off("showEditRomDialog", openHandler);
  emitter?.off("updateUrlCover", urlCoverHandler);
});

const missingCoverImage = computed(() =>
  getMissingCoverImage(rom.value?.name || rom.value?.fs_name || ""),
);

const validForm = computed(() => !!(rom.value?.name && rom.value?.fs_name));

const isFolderRom = computed(
  () =>
    !!rom.value &&
    (rom.value.has_nested_single_file || rom.value.has_multiple_files),
);

const fullPath = computed(() => {
  if (!rom.value) return "";
  return `/romm/library/${rom.value.fs_path}/${rom.value.fs_name}`;
});

// ── Tabbed editing surface ───────────────────────────────────────
// "Details" + "Metadata IDs" are always present; each provider with a
// populated id appends its own tab so the raw-JSON editing surface
// only ever shows panels that actually have data.
interface ProviderConfig {
  /** Tab id — also the discriminant for the rendered panel. */
  tabId: string;
  idField: keyof SimpleRom;
  metadataField: keyof SimpleRom;
  label: string;
  /** Public asset path for the provider logo. Surfaced in the tab nav
   *  next to the label so the surface reads as "you're editing IGDB's
   *  payload" without having to read the text. */
  iconSrc: string;
}

const PROVIDERS: readonly ProviderConfig[] = [
  {
    tabId: "igdb",
    idField: "igdb_id",
    metadataField: "igdb_metadata",
    label: "IGDB",
    iconSrc: "/assets/scrappers/igdb.png",
  },
  {
    tabId: "moby",
    idField: "moby_id",
    metadataField: "moby_metadata",
    label: "MobyGames",
    iconSrc: "/assets/scrappers/moby.png",
  },
  {
    tabId: "ss",
    idField: "ss_id",
    metadataField: "ss_metadata",
    label: "ScreenScraper",
    iconSrc: "/assets/scrappers/ss.png",
  },
  {
    tabId: "launchbox",
    idField: "launchbox_id",
    metadataField: "launchbox_metadata",
    label: "LaunchBox",
    iconSrc: "/assets/scrappers/launchbox.png",
  },
  {
    tabId: "hasheous",
    idField: "hasheous_id",
    metadataField: "hasheous_metadata",
    label: "Hasheous",
    iconSrc: "/assets/scrappers/hasheous.png",
  },
  {
    tabId: "flashpoint",
    idField: "flashpoint_id",
    metadataField: "flashpoint_metadata",
    label: "Flashpoint",
    iconSrc: "/assets/scrappers/flashpoint.png",
  },
  {
    tabId: "hltb",
    idField: "hltb_id",
    metadataField: "hltb_metadata",
    label: "HLTB",
    iconSrc: "/assets/scrappers/hltb.png",
  },
];

const activeTab = ref<string>("details");

const visibleProviders = computed(() =>
  rom.value ? PROVIDERS.filter((p) => rom.value?.[p.idField]) : [],
);

const tabItems = computed<RTabNavItem[]>(() => [
  {
    id: "details",
    label: t("rom.additional-details"),
    icon: "mdi-text-box-plus-outline",
  },
  {
    id: "ids",
    label: t("rom.metadata-ids"),
    icon: "mdi-database",
  },
  ...visibleProviders.value.map((p) => ({
    id: p.tabId,
    label: p.label,
    image: p.iconSrc,
  })),
]);

const activeProvider = computed(() =>
  visibleProviders.value.find((p) => p.tabId === activeTab.value),
);

// When the active provider tab vanishes (unmatch / id wiped), fall back
// to "details" so the content area never points at a missing tab.
watch(tabItems, (items) => {
  if (!items.some((t) => t.id === activeTab.value)) {
    activeTab.value = "details";
  }
});

function previewImage(event: Event) {
  if (!rom.value) return;
  const input = event.target as HTMLInputElement;
  if (!input.files || !input.files[0]) return;

  rom.value.artwork = input.files[0];
  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString() || "";
    removeCover.value = false;
  };
  reader.readAsDataURL(input.files[0]);
}

function setUrlCover(coverUrl: string) {
  if (!coverUrl || !rom.value) return;
  rom.value.url_cover = coverUrl;
  imagePreviewUrl.value = coverUrl;
  removeCover.value = false;
}

function removeArtwork() {
  imagePreviewUrl.value = missingCoverImage.value;
  removeCover.value = true;
}

async function handleRomUpdate(
  options: { rom: UpdateRom; removeCover?: boolean; unmatch?: boolean },
  successMessage: string,
) {
  if (saving.value) return;
  saving.value = true;
  try {
    const { data } = await romApi.updateRom(options);
    snackbar.success(successMessage, { icon: "mdi-check-bold" });
    romsStore.update(data as SimpleRom);
    if (route.name === "rom") romsStore.currentRom = data;
  } catch (error: unknown) {
    console.error(error);
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(axiosErr.response?.data?.detail ?? t("rom.update-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    saving.value = false;
    closeDialog();
  }
}

async function unmatchRom() {
  if (!rom.value) return;
  await handleRomUpdate(
    { rom: rom.value, unmatch: true },
    t("rom.unmatch-success"),
  );
}

async function updateRom() {
  if (!rom.value?.fs_name) {
    snackbar.error(t("rom.filename-required"), { icon: "mdi-close-circle" });
    return;
  }
  await handleRomUpdate(
    { rom: rom.value, removeCover: removeCover.value },
    t("rom.update-success"),
  );
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  imagePreviewUrl.value = "";
}

function handleRomUpdateFromMetadata(updatedRom: UpdateRom) {
  rom.value = updatedRom as EditableRom;
}
</script>

<template>
  <RDialog
    v-if="rom"
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    full-height-on-mobile
    :width="lgAndUp ? 900 : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.edit-rom") }}</span>
    </template>

    <template #content>
      <!-- Hero row — cover + identity fields. Everything else hangs
           off the accordion below. -->
      <div class="r-v2-edit__hero">
        <div class="r-v2-edit__cover-col">
          <GameCard
            :rom="rom"
            :cover-src="imagePreviewUrl"
            size="lg"
            :show-title="false"
            static
            no-hover
          />
          <div class="r-v2-edit__cover-actions">
            <RBtn
              icon="mdi-image-search-outline"
              variant="outlined"
              density="compact"
              :tooltip="t('rom.search-cover')"
              :disabled="
                !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED
              "
              @click="
                emitter?.emit('showSearchCoverDialog', {
                  term: rom.name || rom.fs_name,
                  platformId: rom.platform_id,
                  rom,
                })
              "
            />
            <RBtn
              icon="mdi-pencil"
              variant="outlined"
              density="compact"
              :tooltip="t('rom.upload-cover')"
              @click="coverFileInput?.click()"
            />
            <input
              ref="coverFileInput"
              type="file"
              accept="image/*"
              :aria-label="t('rom.upload-cover')"
              class="r-v2-edit__file"
              @change="previewImage"
            />
            <RBtn
              icon="mdi-delete"
              variant="outlined"
              density="compact"
              color="danger"
              :tooltip="t('rom.remove-cover')"
              @click="removeArtwork"
            />
          </div>
        </div>

        <div class="r-v2-edit__fields">
          <RTextField
            v-model="rom.name"
            prefix-label="stacked"
            hide-details
            :rules="[(v: string) => !!v || t('common.required')]"
          >
            <template #prefix-label>
              <RIcon icon="mdi-format-title" size="14" />
              {{ t("common.name") }}
            </template>
          </RTextField>

          <RTextField
            v-model="rom.name_sort_key"
            prefix-label="stacked"
            hide-details
          >
            <template #prefix-label>
              <RIcon icon="mdi-sort-alphabetical-variant" size="14" />
              {{ t("rom.sort-key") }}
            </template>
          </RTextField>

          <RTextField
            v-model="rom.fs_name"
            prefix-label="stacked"
            hide-details
            :rules="[(v: string) => !!v || t('common.required')]"
          >
            <template #prefix-label>
              <RIcon
                :icon="isFolderRom ? 'mdi-folder-outline' : 'mdi-file-outline'"
                size="14"
              />
              {{ isFolderRom ? t("rom.folder-name") : t("rom.filename") }}
            </template>
            <template #subtitle>
              <RIcon icon="mdi-folder-file-outline" size="13" color="primary" />
              {{ fullPath }}
            </template>
          </RTextField>

          <RTextField
            v-model="rom.summary"
            prefix-label="stacked"
            hide-details
            multiline
            :rows="3"
          >
            <template #prefix-label>
              <RIcon icon="mdi-text" size="14" />
              {{ t("rom.summary") }}
            </template>
          </RTextField>
        </div>
      </div>

      <!-- Tabbed editing surface — "Details" + "Metadata IDs" always
           present, one tab per provider with a populated id appended
           after. Sits under the hero so the dialog reads top-down as
           "identity → editing surface". -->
      <div class="r-v2-edit__panels">
        <RTabNav
          v-model="activeTab"
          :items="tabItems"
          variant="underlined"
          size="small"
          :aria-label="t('rom.edit-rom-sections')"
        />
        <div class="r-v2-edit__tab-content">
          <AdditionalDetails
            v-if="activeTab === 'details'"
            :rom="rom"
            @update:rom="handleRomUpdateFromMetadata"
          />
          <MetadataIdSection
            v-else-if="activeTab === 'ids'"
            :rom="rom"
            @update:rom="handleRomUpdateFromMetadata"
          />
          <RawMetadataPanel
            v-else-if="activeProvider"
            :key="activeProvider.tabId"
            :rom="rom"
            :metadata-field="activeProvider.metadataField as keyof UpdateRom"
            :label="activeProvider.label"
            @update:rom="handleRomUpdateFromMetadata"
          />
        </div>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="saving" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        v-if="!rom.is_unidentified"
        variant="outlined"
        color="error"
        prepend-icon="mdi-link-variant-off"
        :loading="saving"
        :disabled="saving"
        @click="unmatchRom"
      >
        {{ t("rom.unmatch") }}
      </RBtn>
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-check"
        :loading="saving"
        :disabled="!validForm || saving"
        @click="updateRom"
      >
        {{ t("common.apply") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
/* ── Hero ──────────────────────────────────────────────────────────
   Cover column sizes to the cover's natural width (`auto`) so the gap to
   the fields is exactly the grid `gap`, consistent for any cover shape —
   a fixed-width column would leave variable leftover space beside a
   natural-width cover. `align-items: start` keeps the cover anchored to
   the top so taller field stacks (or the growing summary) don't drag it
   down. */
.r-v2-edit__hero {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 24px;
  align-items: start;
}

.r-v2-edit__cover-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.r-v2-edit__cover-actions {
  display: flex;
  gap: 4px;
}

.r-v2-edit__fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.r-v2-edit__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

/* ── Tab surface ─────────────────────────────────────────────────
   The tab nav owns its own bottom border, so the only separator we
   need above is breathing space — the hero ends, the dialog body's
   flex gap beats, then the tab strip begins. The tab content gets its
   own inset so panels don't sit flush against the underlined strip. */
.r-v2-edit__panels {
  display: flex;
  flex-direction: column;
}

.r-v2-edit__tab-content {
  padding-top: 16px;
}

/* ── Compact breakpoint ───────────────────────────────────────────
   Cover stacks above the fields when the dialog is forced narrow. */
html[data-bp~="xs"] .r-v2-edit__hero {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-edit__cover-col {
  max-width: 240px;
  margin: 0 auto;
}
</style>
