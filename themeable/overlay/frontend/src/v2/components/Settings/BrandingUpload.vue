<script setup lang="ts">
// BrandingUpload (romm-themeable): the "Upload a theme pack" control at the top of Branding.
import { RAlert, RDropzone, RSpinner } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { BrandingStatus, PackClash } from "@/services/api/themeable";
import { useConfirm } from "@/v2/composables/useConfirm";
import { PACK_EXTENSION, usePackUpload } from "@/v2/composables/usePackUpload";

const props = defineProps<{
  maxBytes: number;
  disabled?: boolean;
}>();

const emit = defineEmits<{ uploaded: [status: BrandingStatus] }>();

const { t } = useI18n();
const confirm = useConfirm();

function confirmReplace(clash: PackClash): Promise<boolean> {
  return confirm({
    title: t("branding.replace-title", { id: clash.id }),
    body: t("branding.replace-body", { name: clash.name }),
    confirmText: t("branding.replace"),
    tone: "warning",
  });
}

const { upload, uploading, error, problems } = usePackUpload(
  () => props.maxBytes,
  confirmReplace,
);
const maxMb = computed(() => Math.floor(props.maxBytes / (1024 * 1024)));

async function onFiles(files: File[]): Promise<void> {
  const [file] = files;
  if (!file) return;
  const status = await upload(file);
  if (status) emit("uploaded", status);
}
</script>

<template>
  <div class="r-v2-branding-upload">
    <RDropzone
      compact
      :accept="`${PACK_EXTENSION},application/zip`"
      :disabled="disabled || uploading"
      :title="t('branding.upload-title')"
      :hint="t('branding.upload-hint', { mb: maxMb })"
      :active-title="t('branding.upload-drop')"
      :input-label="t('branding.upload-title')"
      icon="mdi-folder-zip-outline"
      @files="onFiles"
    >
      <template v-if="uploading" #actions>
        <span class="r-v2-branding-upload__busy">
          <RSpinner :size="16" />
          {{ t("branding.uploading") }}
        </span>
      </template>
    </RDropzone>
    <RAlert v-if="error" type="error" density="compact">
      {{ error }}
      <ul v-if="problems.length" class="r-v2-branding-upload__problems">
        <li v-for="(problem, i) in problems" :key="i">{{ problem }}</li>
      </ul>
    </RAlert>
  </div>
</template>

<style scoped>
.r-v2-branding-upload {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-v2-branding-upload__busy {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-branding-upload__problems {
  margin: var(--r-space-1) 0 0;
  padding-left: var(--r-space-4);
}
</style>
