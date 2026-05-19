<script setup lang="ts">
// RawMetadataPanel (v2) — body for the per-provider collapsibles in
// MetadataSections. The wrapping RCollapsible (with avatar + label) is
// owned by the parent; this component owns the textarea + action row.
//
// Feature composite — knows the UpdateRom shape and the emitter event
// bus. Renders nothing if the rom has no stored data for the configured
// provider.
import { RBtn, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref } from "vue";
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

const fieldLabel = computed(() => `${props.label} ${t("rom.metadata")} JSON`);
</script>

<template>
  <div v-if="hasMetadata" class="r-v2-raw-meta">
    <RTextField
      v-model="metadataJson"
      :label="fieldLabel"
      prefix-label="stacked"
      variant="outlined"
      :readonly="!isEditing"
      multiline
      :rows="8"
      mono
      hide-details
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
  gap: 8px;
}

.r-v2-raw-meta__actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 2px;
}
</style>
