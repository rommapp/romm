<script setup lang="ts">
// ScreenshotsSubtab: the Media tab's Screenshots panel. Four sections, each
// screenshot pinnable to the Overview tab:
//
//   * Scraped: screenshots fetched from metadata providers (read-only).
//   * ROM        — shared library screenshots stored in the ROM's
//                  `screenshots/` folder (RomFile, category SCREENSHOT). A
//                  single-file ROM is promoted to a folder on upload. Public to
//                  every user who can see the ROM. Upload → `useRomFileUpload`.
//   * Mine       — per-user screenshots stored under the user's asset folder.
//                  Private by default; each one's edit dialog shares it.
//                  Any ROM. Upload → `screenshotApi.uploadGalleryScreenshots`.
//   * Community  — other users' public per-user screenshots (read-only).
//
// Both uploadable sections use RDropzone (CTA when empty, overlay over the
// grid when filled).
import { RBtn, RDropzone } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, defineAsyncComponent, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import screenshotApi from "@/services/api/screenshot";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import ScreenshotEditDialog from "@/v2/components/GameDetails/ScreenshotEditDialog.vue";
import type { ScreenshotItem } from "@/v2/components/GameDetails/ScreenshotsTab.vue";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { usePinnedMedia } from "@/v2/composables/usePinnedMedia";
import {
  ROM_UPLOAD_FOLDERS,
  useRomFileUpload,
} from "@/v2/composables/useRomFileUpload";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";
import { mediaKey } from "@/v2/utils/mediaKeys";
import { romFolderScreenshots } from "@/v2/utils/pinnedMedia";
import { versionedRomFileUrl } from "@/v2/utils/romFiles";

const ScreenshotsTab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ScreenshotsTab.vue"),
);

const props = defineProps<{ rom: DetailedRom }>();

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { refetchRom } = useRomSync();
const { uploadFiles } = useRomFileUpload();
const uploadStore = storeUpload();
const authStore = storeAuth();
const { user } = storeToRefs(authStore);

// The shared ROM section writes to the ROM itself (roms.write); the "Mine"
// section writes per-user assets and stays available to everyone.
const canEditRom = useCan("rom.edit");

const { isPinned, togglePin } = usePinnedMedia(() => props.rom);

const scrapedScreenshots = computed<ScreenshotItem[]>(() =>
  (props.rom.merged_screenshots ?? []).map((url) => ({
    url,
    pinKey: mediaKey.scraped(url),
  })),
);

// ---------- ROM (shared) screenshots — RomFile-backed ----------
const romScreenshots = computed<ScreenshotItem[]>(() =>
  romFolderScreenshots(props.rom).map((file) => ({
    id: file.id,
    url: versionedRomFileUrl(file),
    pinKey: mediaKey.file(file.id),
  })),
);

// ---------- Per-user screenshots — asset-backed ----------
const allUserScreenshots = computed(() => props.rom.all_user_screenshots ?? []);

const myScreenshots = computed<ScreenshotItem[]>(() =>
  allUserScreenshots.value
    .filter((s) => user.value?.id != null && s.user_id === user.value.id)
    .map((s) => ({
      id: s.id,
      url: s.download_path,
      pinKey: mediaKey.screenshot(s.id),
      isOwn: true,
      isPublic: Boolean(s.is_public),
    })),
);

const communityScreenshots = computed<ScreenshotItem[]>(() =>
  allUserScreenshots.value
    .filter((s) => user.value?.id == null || s.user_id !== user.value.id)
    .map((s) => ({
      id: s.id,
      url: s.download_path,
      pinKey: mediaKey.screenshot(s.id),
      isOwn: false,
      isPublic: true,
      username: s.username,
      userId: s.user_id,
      userAvatarPath: s.user_avatar_path,
      userUpdatedAt: s.user_updated_at,
    })),
);

async function refreshRom() {
  await refetchRom(props.rom.id);
}

// ---------- Upload result toast for the per-user gallery ----------
function reportUpload(responses: PromiseSettledResult<unknown>[]) {
  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;
  if (failed === 0) uploadStore.reset();
  if (successful > 0) {
    snackbar.success(
      failed
        ? t("rom.screenshots-uploaded-with-failed", successful, {
            named: { n: successful, failed },
          })
        : t("rom.screenshots-uploaded-n", successful, {
            named: { n: successful },
          }),
      { icon: "mdi-check-bold", timeout: 3000 },
    );
  } else {
    snackbar.warning(t("rom.no-screenshots-uploaded"), {
      icon: "mdi-close-circle",
      timeout: 5000,
    });
  }
}

// ---------- Upload handlers (wired to RDropzone @files) ----------
const romDz = ref<InstanceType<typeof RDropzone> | null>(null);
const myDz = ref<InstanceType<typeof RDropzone> | null>(null);

async function handleRomFiles(files: File[]) {
  await uploadFiles(props.rom, ROM_UPLOAD_FOLDERS.screenshots, files);
}

async function handleMyFiles(files: File[]) {
  if (files.length === 0) return;
  const responses = await screenshotApi.uploadGalleryScreenshots({
    romId: props.rom.id,
    filesToUpload: files,
  });
  reportUpload(responses);
  if (responses.some((r) => r.status === "fulfilled")) await refreshRom();
}

// ---------- Delete ----------
async function deleteRomScreenshot(fileId: number) {
  const file = (props.rom.files ?? []).find((f) => f.id === fileId);
  const name = file?.file_name ?? "";
  const ok = await confirm({
    title: t("rom.delete-screenshot-title"),
    body: name
      ? t("rom.delete-screenshot-body-named", { name })
      : t("rom.delete-screenshot-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await romApi.removeScreenshot({ romId: props.rom.id, fileId });
    await refreshRom();
    snackbar.success(t("rom.screenshot-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.screenshot-remove-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  }
}

async function deleteMyScreenshot(id: number) {
  const ok = await confirm({
    title: t("rom.delete-screenshot-title"),
    body: t("rom.delete-screenshot-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await screenshotApi.deleteScreenshot({ id });
    await refreshRom();
    snackbar.success(t("rom.screenshot-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.screenshot-remove-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  }
}

// ---------- Edit ----------
const editTarget = ref<ScreenshotItem | null>(null);
const savingEdit = ref(false);

async function submitEdit(isPublic: boolean) {
  const target = editTarget.value;
  if (!target?.id || savingEdit.value) return;
  savingEdit.value = true;
  try {
    await screenshotApi.setScreenshotVisibility({ id: target.id, isPublic });
    await refreshRom();
    if (editTarget.value === target) editTarget.value = null;
    snackbar.success(t("rom.screenshot-updated"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("common.cant-update-visibility", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    savingEdit.value = false;
  }
}
</script>

<template>
  <div class="r-v2-shots">
    <section v-if="scrapedScreenshots.length > 0" class="r-v2-shots__section">
      <header class="r-v2-shots__head">
        <div class="r-v2-shots__head-text">
          <h3 class="r-v2-shots__title">
            {{ t("rom.screenshots-section-scraped") }}
          </h3>
          <p class="r-v2-shots__subtitle">
            {{ t("rom.screenshots-section-scraped-desc") }}
          </p>
        </div>
      </header>
      <ScreenshotsTab
        :screenshots="scrapedScreenshots"
        :is-pinned="isPinned"
        @toggle-pin="togglePin"
      />
    </section>

    <!-- ROM (shared) screenshots — the whole section drops away for a
         read-only user with nothing to show, since there is neither art to
         look at nor an upload they're allowed to make. -->
    <section
      v-if="canEditRom || romScreenshots.length > 0"
      class="r-v2-shots__section"
    >
      <header class="r-v2-shots__head">
        <div class="r-v2-shots__head-text">
          <h3 class="r-v2-shots__title">
            {{ t("rom.screenshots-section-rom") }}
          </h3>
          <p class="r-v2-shots__subtitle">
            {{ t("rom.screenshots-section-rom-desc") }}
          </p>
        </div>
        <RBtn
          v-if="romScreenshots.length > 0 && canEditRom"
          variant="outlined"
          size="small"
          prepend-icon="mdi-cloud-upload-outline"
          @click="romDz?.open()"
        >
          {{ t("common.upload") }}
        </RBtn>
      </header>

      <RDropzone
        v-if="romScreenshots.length === 0"
        :title="t('rom.screenshots-empty')"
        :hint="t('common.dropzone-hint')"
        :active-title="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-screenshots')"
        accept="image/*"
        multiple
        @files="handleRomFiles"
      />
      <RDropzone
        v-else
        ref="romDz"
        overlay
        :disabled="!canEditRom"
        :release-label="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-screenshots')"
        accept="image/*"
        multiple
        @files="handleRomFiles"
      >
        <ScreenshotsTab
          :screenshots="romScreenshots"
          :deletable="canEditRom"
          :is-pinned="isPinned"
          @delete="deleteRomScreenshot"
          @toggle-pin="togglePin"
        />
      </RDropzone>
    </section>

    <!-- My (per-user) screenshots -->
    <section class="r-v2-shots__section">
      <header class="r-v2-shots__head">
        <div class="r-v2-shots__head-text">
          <h3 class="r-v2-shots__title">
            {{ t("rom.screenshots-section-mine") }}
          </h3>
        </div>
        <RBtn
          v-if="myScreenshots.length > 0"
          variant="outlined"
          size="small"
          prepend-icon="mdi-cloud-upload-outline"
          @click="myDz?.open()"
        >
          {{ t("common.upload") }}
        </RBtn>
      </header>

      <RDropzone
        v-if="myScreenshots.length === 0"
        :title="t('rom.screenshots-empty')"
        :hint="t('common.dropzone-hint')"
        :active-title="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-screenshots')"
        accept="image/*"
        multiple
        @files="handleMyFiles"
      />
      <RDropzone
        v-else
        ref="myDz"
        overlay
        :release-label="t('common.dropzone-drag-over')"
        :input-label="t('rom.upload-screenshots')"
        accept="image/*"
        multiple
        @files="handleMyFiles"
      >
        <ScreenshotsTab
          :screenshots="myScreenshots"
          deletable
          editable
          :is-pinned="isPinned"
          @edit="editTarget = $event"
          @delete="deleteMyScreenshot"
          @toggle-pin="togglePin"
        />
      </RDropzone>
    </section>

    <!-- Community (others' public) screenshots -->
    <section v-if="communityScreenshots.length > 0" class="r-v2-shots__section">
      <header class="r-v2-shots__head">
        <div class="r-v2-shots__head-text">
          <h3 class="r-v2-shots__title">
            {{ t("rom.screenshots-section-community") }}
          </h3>
        </div>
      </header>
      <ScreenshotsTab
        :screenshots="communityScreenshots"
        :is-pinned="isPinned"
        @toggle-pin="togglePin"
      />
    </section>

    <ScreenshotEditDialog
      :model-value="editTarget !== null"
      :is-public="!!editTarget?.isPublic"
      :busy="savingEdit"
      @update:model-value="!$event && (editTarget = null)"
      @submit="submitEdit"
    />
  </div>
</template>

<style scoped>
.r-v2-shots {
  display: flex;
  flex-direction: column;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}

.r-v2-shots__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-shots__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.r-v2-shots__title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-shots__subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
