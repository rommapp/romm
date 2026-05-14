<script setup lang="ts">
// RawMetadataPanel (v2) — one collapsible per metadata provider that
// has a stored payload. Lets admins read or hand-edit the raw JSON
// (debug shape, override broken keys, …). Renders nothing if the rom
// has no stored data for the configured provider.
//
// Feature composite — knows the UpdateRom shape and the emitter event
// bus. The collapsible chrome is owned by the parent (MetadataSections
// renders an RCollapsible around each panel), so this component only
// owns the body + action row.
import { RBtn } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref, useId } from "vue";
import { useI18n } from "vue-i18n";
import type { UpdateRom } from "@/services/api/rom";
import type { Events } from "@/types/emitter";

interface Props {
  rom: UpdateRom;
  metadataField: keyof UpdateRom;
  label: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");

const textareaId = useId();

const isEditing = ref(false);
const metadataJson = ref("");

const hasMetadata = computed(() => Boolean(props.rom[props.metadataField]));

function initializeMetadata() {
  const metadata = props.rom[props.metadataField];
  metadataJson.value = metadata ? JSON.stringify(metadata, null, 2) : "";
  isEditing.value = false;
}

onMounted(initializeMetadata);

function startEdit() {
  isEditing.value = true;
}

function cancelEdit() {
  initializeMetadata();
}

function saveMetadata() {
  // Empty wipe — reset this provider's slot to `{}` in raw_metadata.
  if (!metadataJson.value || metadataJson.value.trim() === "") {
    emit("update:rom", {
      ...props.rom,
      raw_metadata: {
        ...props.rom.raw_metadata,
        [props.metadataField]: "{}",
      },
    });
    isEditing.value = false;
    return;
  }

  try {
    JSON.parse(metadataJson.value);
    emit("update:rom", {
      ...props.rom,
      raw_metadata: {
        ...props.rom.raw_metadata,
        [props.metadataField]: metadataJson.value,
      },
    });
    isEditing.value = false;
  } catch {
    emitter?.emit("snackbarShow", {
      msg: "Invalid JSON format",
      icon: "mdi-close-circle",
      color: "red",
      timeout: 3000,
    });
  }
}
</script>

<template>
  <div v-if="hasMetadata" class="r-v2-raw-meta">
    <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -->
    <label :for="textareaId" class="r-v2-raw-meta__label">
      {{ label }} {{ t("rom.metadata") }} JSON
    </label>
    <textarea
      :id="textareaId"
      v-model="metadataJson"
      class="r-v2-raw-meta__textarea"
      :class="{ 'r-v2-raw-meta__textarea--readonly': !isEditing }"
      :readonly="!isEditing"
      rows="8"
      spellcheck="false"
    />
    <div class="r-v2-raw-meta__actions">
      <RBtn
        v-if="!isEditing"
        variant="text"
        color="primary"
        prepend-icon="mdi-pencil-outline"
        @click="startEdit"
      >
        {{ t("common.edit") }}
      </RBtn>
      <template v-else>
        <RBtn variant="text" color="danger" @click="cancelEdit">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          variant="translucent"
          color="success"
          prepend-icon="mdi-check"
          @click="saveMetadata"
        >
          {{ t("common.save") }}
        </RBtn>
      </template>
    </div>
  </div>
</template>

<style scoped>
.r-v2-raw-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-raw-meta__label {
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}

.r-v2-raw-meta__textarea {
  /* Match the RTextField outlined chrome so the panel feels consistent
     with the rest of the dialog's inputs. */
  font-family: var(--r-font-family-mono);
  font-size: 12px;
  line-height: 1.45;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--r-color-border-strong);
  border-radius: 8px;
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg);
  resize: vertical;
  min-height: 140px;
  outline: none;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-raw-meta__textarea:focus-visible {
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
}
.r-v2-raw-meta__textarea--readonly {
  background: transparent;
  cursor: default;
}

.r-v2-raw-meta__actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 2px;
}
</style>
