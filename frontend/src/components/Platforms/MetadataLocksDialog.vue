<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RCheckbox, RDialog, RSelect } from "@/lib";
import romApi, { type MetadataLockField } from "@/services/api/rom";
import type { Platform } from "@/stores/platforms";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue: boolean;
  platforms: Platform[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const allLibrary = ref(true);
const platformId = ref<number | null>(null);
const locked = ref(true);
const selectedFields = ref<MetadataLockField[]>([]);
const saving = ref(false);

const fields = computed<{ id: MetadataLockField; label: string }[]>(() => [
  { id: "name", label: t("common.name") },
  { id: "summary", label: t("rom.summary") },
  { id: "cover", label: t("rom.media-cover") },
  { id: "screenshots", label: t("rom.screenshots") },
  { id: "manual", label: t("rom.manual") },
  { id: "genres", label: t("rom.genres") },
  { id: "franchises", label: t("rom.franchises") },
  { id: "collections", label: t("rom.collections") },
  { id: "companies", label: t("rom.companies") },
  { id: "game_modes", label: t("rom.game-modes") },
  { id: "age_ratings", label: t("rom.age-ratings") },
  { id: "first_release_date", label: t("rom.released-at") },
  { id: "player_count", label: t("rom.player-count") },
]);

const platformItems = computed(() =>
  props.platforms.map((platform) => ({
    title: platform.display_name,
    value: Number(platform.id),
  })),
);
const actionItems = computed(() => [
  { title: t("rom.lock-metadata"), value: true },
  { title: t("rom.unlock-metadata"), value: false },
]);
const canSubmit = computed(
  () =>
    selectedFields.value.length > 0 &&
    (allLibrary.value || platformId.value !== null) &&
    !saving.value,
);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    allLibrary.value = true;
    platformId.value = null;
    locked.value = true;
    selectedFields.value = [];
  },
);

function toggleField(field: MetadataLockField, checked: boolean) {
  selectedFields.value = checked
    ? [...new Set([...selectedFields.value, field])]
    : selectedFields.value.filter((item) => item !== field);
}

async function submit() {
  if (!canSubmit.value) return;
  saving.value = true;
  try {
    const { data } = await romApi.updateBulkMetadataLocks({
      fields: selectedFields.value,
      locked: locked.value,
      ...(allLibrary.value ? { all: true } : { platform_id: platformId.value }),
    });
    snackbar.success(
      t("rom.bulk-metadata-lock-result", {
        updated: data.updated,
        failed: data.failed,
      }),
      { icon: "mdi-check-bold" },
    );
    emit("update:modelValue", false);
  } catch {
    snackbar.error(t("rom.update-failed"), { icon: "mdi-close-circle" });
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <RDialog
    v-bind="$attrs"
    :model-value="modelValue"
    icon="mdi-lock-outline"
    width="640"
    scroll-content
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>{{ t("rom.bulk-metadata-lock") }}</template>
    <template #content>
      <div class="r-metadata-locks">
        <RCheckbox
          :model-value="allLibrary"
          :label="t('rom.metadata-lock-library')"
          @update:model-value="allLibrary = $event"
        />
        <RSelect
          v-if="!allLibrary"
          v-model="platformId"
          :items="platformItems"
          :label="t('rom.metadata-lock-platform')"
          variant="outlined"
        />
        <RSelect
          v-model="locked"
          :items="actionItems"
          :label="t('rom.metadata-lock-action')"
          variant="outlined"
        />
        <div class="r-metadata-locks__fields">
          <RCheckbox
            v-for="field in fields"
            :key="field.id"
            :model-value="selectedFields.includes(field.id)"
            :label="field.label"
            @update:model-value="toggleField(field.id, $event)"
          />
        </div>
      </div>
    </template>
    <template #footer>
      <RBtn
        variant="translucent"
        color="primary"
        :loading="saving"
        :disabled="!canSubmit"
        @click="submit"
      >
        {{ t("common.apply") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-metadata-locks {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-metadata-locks__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--r-space-2) var(--r-space-3);
}
</style>
