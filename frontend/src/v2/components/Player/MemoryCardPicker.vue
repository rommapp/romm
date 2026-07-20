<script setup lang="ts">
// MemoryCardPicker: picks which whole memory card gets hydrated onto the
// streaming container at claim (PCSX2 whole-card sync). Shows the user's own
// cards for this emulator, newest-first, and lets them mint a fresh named
// card inline. The selected card id rides along to claimSession as the third
// argument.
//
// Semantics: the model is the card id, or null. Null is a valid state: when
// the user has no cards (or clears the choice) the backend picks their newest
// card for the emulator, or auto-creates a blank one at claim. So an empty
// list is not an error; it just means "a blank card will be created".
//
// Cards key HARD on `emulator` (that is what claim-time lookup uses); the
// optional `platformId` is a display/creation hint only and never scopes the
// fetch.
import { RBtn, RDialog, RForm, RIcon, RSelect, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { MemoryCardSchema } from "@/__generated__";
import memoryCardApi from "@/services/api/memory-card";
import MemoryCardManager from "@/v2/components/Player/MemoryCardManager.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { required } from "@/v2/utils/validation";

const props = defineProps<{
  emulator: string;
  platformId?: number | null;
  modelValue?: number | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: number | null): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();

const cards = ref<MemoryCardSchema[]>([]);
const loading = ref(false);

const cardItems = computed(() =>
  cards.value.map((c) => ({ title: c.name, value: c.id })),
);

// Fetch the caller's cards for this emulator whenever the emulator changes,
// then preselect the newest (first) so Play resumes the last-used card.
// Best-effort: a fetch failure leaves the list empty (blank card at claim)
// rather than blocking launch.
async function loadCards(emulator: string): Promise<void> {
  if (!emulator) return;
  loading.value = true;
  try {
    const { data } = await memoryCardApi.getMemoryCards({ emulator });
    cards.value = data;
    preselect();
  } catch (err) {
    console.warn("[memory-cards] Could not fetch cards:", err);
    cards.value = [];
  } finally {
    loading.value = false;
  }
}

// Keep the selection valid: clear it if the chosen card vanished, and default
// to the newest card when nothing is selected yet.
function preselect(): void {
  const current = props.modelValue;
  if (current != null && !cards.value.some((c) => c.id === current)) {
    emit("update:modelValue", null);
  }
  if (props.modelValue == null && cards.value.length > 0) {
    emit("update:modelValue", cards.value[0].id);
  }
}

watch(() => props.emulator, loadCards, { immediate: true });

function onSelect(value: unknown): void {
  emit("update:modelValue", typeof value === "number" ? value : null);
}

// ── Create dialog ───────────────────────────────────────────────────
const showCreate = ref(false);
const creating = ref(false);
const formValid = ref(true);
const newName = ref("");

const nameRules = [required(t("common.required"))];

function openCreate(): void {
  newName.value = "";
  showCreate.value = true;
}

// ── Manage dialog ───────────────────────────────────────────────────
const showManage = ref(false);

function onManaged(): void {
  // A rename/share/delete happened in the manager; refresh so the select
  // reflects the change (and drops a card the user just deleted).
  void loadCards(props.emulator);
}

async function submitCreate(): Promise<void> {
  const name = newName.value.trim();
  if (!name || creating.value) return;
  creating.value = true;
  try {
    const { data } = await memoryCardApi.createMemoryCard({
      name,
      emulator: props.emulator,
      platform_id: props.platformId ?? null,
    });
    // Newest-first, so the fresh card leads the list and becomes the choice.
    cards.value = [data, ...cards.value];
    emit("update:modelValue", data.id);
    showCreate.value = false;
    snackbar.success(t("play.memory-card-created"), { icon: "mdi-check-bold" });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string; detail?: string } };
      message?: string;
    };
    snackbar.error(
      `${t("play.memory-card-create-failed")}: ${
        e?.response?.data?.msg ||
        e?.response?.data?.detail ||
        e?.message ||
        t("common.unknown-error")
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <div class="r-mc-picker">
    <div class="r-mc-picker__row">
      <RSelect
        :model-value="modelValue"
        class="r-mc-picker__select"
        :items="cardItems"
        :loading="loading"
        :disabled="loading || cards.length === 0"
        variant="outlined"
        density="comfortable"
        prepend-inner-icon="mdi-sd"
        hide-details
        :label="t('play.memory-card')"
        :placeholder="
          cards.length === 0 ? t('play.no-memory-cards') : undefined
        "
        @update:model-value="onSelect"
      />
      <RBtn
        icon="mdi-plus"
        variant="text"
        :tooltip="t('play.new-memory-card')"
        :disabled="loading"
        @click="openCreate"
      />
      <RBtn
        icon="mdi-cog-outline"
        variant="text"
        :tooltip="t('play.manage-memory-cards')"
        :disabled="loading || cards.length === 0"
        @click="showManage = true"
      />
    </div>

    <RDialog
      v-model="showCreate"
      icon="mdi-sd"
      :width="420"
      @close="showCreate = false"
    >
      <template #header>
        <span>{{ t("play.create-memory-card") }}</span>
      </template>

      <template #content>
        <RForm v-model="formValid" @submit="submitCreate">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
          <RTextField
            v-model="newName"
            :placeholder="t('common.name')"
            prefix-label="stacked"
            :rules="nameRules"
            required
            autofocus
          >
            <template #prefix-label>
              {{ t("common.name") }}
            </template>
          </RTextField>
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
        </RForm>
      </template>

      <template #footer>
        <RBtn variant="text" :disabled="creating" @click="showCreate = false">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="!newName.trim() || creating"
          :loading="creating"
          @click="submitCreate"
        >
          {{ t("common.create") }}
        </RBtn>
      </template>
    </RDialog>

    <RDialog
      v-model="showManage"
      icon="mdi-sd"
      :width="560"
      scroll-content
      @close="showManage = false"
    >
      <template #header>
        <span>{{ t("play.manage-memory-cards") }}</span>
      </template>
      <template #content>
        <MemoryCardManager
          :emulator="emulator"
          :platform-id="platformId ?? null"
          @changed="onManaged"
        />
      </template>
      <template #footer>
        <RBtn variant="text" @click="showManage = false">
          {{ t("common.close") }}
        </RBtn>
      </template>
    </RDialog>

    <p class="r-mc-picker__hint">
      <RIcon icon="mdi-information-outline" size="12" />
      <span>{{ t("play.memory-card-hint") }}</span>
    </p>
  </div>
</template>

<style scoped>
.r-mc-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-mc-picker__row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.r-mc-picker__select {
  flex: 1 1 auto;
  min-width: 0;
}

.r-mc-picker__hint {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
}
</style>
