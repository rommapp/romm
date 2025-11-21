<script setup lang="ts">
import type { Emitter } from "mitt";
import { ref, computed, onMounted } from "vue";
import { inject } from "vue";
import type { UpdateRom } from "@/services/api/rom";
import type { Events } from "@/types/emitter";

interface Props {
  rom: UpdateRom;
  metadataField: keyof UpdateRom;
  iconSrc: string;
  label: string;
}

const props = defineProps<Props>();
const emitter = inject<Emitter<Events>>("emitter");

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const isEditing = ref(false);
const metadataJson = ref("");

const initializeMetadata = () => {
  const metadata = props.rom[props.metadataField];
  metadataJson.value = metadata ? JSON.stringify(metadata, null, 2) : "";
  isEditing.value = false;
};

onMounted(() => initializeMetadata());

const validateJson = (value: string): boolean | string => {
  if (!value || value.trim() === "") return true;

  try {
    JSON.parse(value);
    return true;
  } catch (error) {
    return "Invalid JSON format";
  }
};

const startEdit = () => {
  isEditing.value = true;
};

const cancelEdit = () => {
  isEditing.value = false;
  initializeMetadata();
};

const saveMetadata = () => {
  if (!metadataJson.value || metadataJson.value.trim() === "") {
    emit("update:rom", {
      ...props.rom,
      raw_metadata: { ...props.rom.raw_metadata, [props.metadataField]: "{}" },
    });
    isEditing.value = false;
    return;
  }

  try {
    JSON.parse(metadataJson.value);

    // Update the ROM with raw metadata
    const updatedRom = {
      ...props.rom,
      raw_metadata: {
        ...props.rom.raw_metadata,
        [props.metadataField]: metadataJson.value,
      },
    };

    emit("update:rom", updatedRom);
    isEditing.value = false;
  } catch (error) {
    emitter?.emit("snackbarShow", {
      msg: "Invalid JSON format",
      icon: "mdi-close-circle",
      color: "red",
      timeout: 3000,
    });
  }
};
</script>

<template>
  <v-expansion-panel v-if="rom[metadataField]" elevation="0">
    <v-expansion-panel-title class="bg-toplayer">
      <v-avatar size="26" rounded class="mr-2">
        <v-img :src="iconSrc" />
      </v-avatar>
      {{ label }} {{ $t("rom.metadata") }}
    </v-expansion-panel-title>
    <v-expansion-panel-text class="mt-4 px-2">
      <v-textarea
        v-model="metadataJson"
        :label="`${label} ${$t('rom.metadata')} JSON`"
        variant="outlined"
        rows="8"
        hide-details
        :readonly="!isEditing"
        :rules="[validateJson]"
      />
      <v-btn-group
        divided
        density="compact"
        rounded="0"
        class="my-2 d-flex justify-center"
      >
        <v-btn
          v-if="!isEditing"
          variant="flat"
          class="text-primary bg-toplayer"
          @click="startEdit"
        >
          {{ $t("common.edit") }}
        </v-btn>
        <template v-else>
          <v-btn
            variant="flat"
            @click="cancelEdit"
            class="text-romm-red bg-toplayer"
          >
            {{ $t("common.cancel") }}
          </v-btn>
          <v-btn
            variant="flat"
            @click="saveMetadata"
            class="text-romm-green bg-toplayer"
          >
            {{ $t("common.save") }}
          </v-btn>
        </template>
      </v-btn-group>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>
