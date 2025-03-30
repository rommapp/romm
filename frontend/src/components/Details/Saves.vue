<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";
import { getEmptyCoverImage } from "@/utils/covers";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const props = defineProps<{ rom: DetailedRom }>();
const selectedSaves = ref<SaveSchema[]>([]);
const lastSelectedIndex = ref<number>(-1);
const emitter = inject<Emitter<Events>>("emitter");

// Functions
async function downloasSaves() {
  selectedSaves.value.map((save) => {
    const a = document.createElement("a");
    a.href = save.download_path;
    a.download = `${save.file_name}`;
    a.click();
  });

  selectedSaves.value = [];
}

function onCardClick(save: SaveSchema, event: MouseEvent) {
  const saveIndex = props.rom.user_saves.indexOf(save);

  if (event.shiftKey && lastSelectedIndex.value !== null) {
    const [startIndex, endIndex] = [lastSelectedIndex.value, saveIndex].sort(
      (a, b) => a - b,
    );
    const rangeSaves = props.rom.user_saves.slice(startIndex, endIndex + 1);

    const isDeselecting = selectedSaves.value.includes(save);

    if (isDeselecting) {
      selectedSaves.value = selectedSaves.value.filter(
        (s) => !rangeSaves.includes(s),
      );
    } else {
      const savesToAdd = rangeSaves.filter(
        (s) => !selectedSaves.value.includes(s),
      );
      selectedSaves.value = [...selectedSaves.value, ...savesToAdd];
    }
  } else {
    const isSelected = selectedSaves.value.includes(save);

    if (isSelected) {
      selectedSaves.value = selectedSaves.value.filter((s) => s.id !== save.id);
    } else {
      selectedSaves.value = [...selectedSaves.value, save];
    }
  }

  lastSelectedIndex.value = saveIndex;
}
</script>

<template>
  <div>
    <v-btn-group divided density="default">
      <v-btn
        v-if="scopes.includes('assets.write')"
        drawer
        size="small"
        @click="emitter?.emit('addSavesDialog', rom)"
      >
        <v-icon>mdi-upload</v-icon>
      </v-btn>
      <v-btn
        drawer
        :disabled="!selectedSaves.length"
        :variant="selectedSaves.length > 0 ? 'flat' : 'plain'"
        size="small"
        @click="downloasSaves"
      >
        <v-icon>mdi-download</v-icon>
      </v-btn>
      <v-btn
        v-if="scopes.includes('assets.write')"
        drawer
        :class="{
          'text-romm-red': selectedSaves.length,
        }"
        :disabled="!selectedSaves.length"
        :variant="selectedSaves.length > 0 ? 'flat' : 'plain'"
        @click="
          emitter?.emit('showDeleteSavesDialog', {
            rom: props.rom,
            saves: selectedSaves,
          })
        "
        size="small"
      >
        <v-icon>mdi-delete</v-icon>
      </v-btn>
    </v-btn-group>
  </div>
  <div class="d-flex ga-4 flex-md-wrap mt-6 px-2">
    <v-hover
      v-if="rom.user_saves.length > 0"
      v-for="save in rom.user_saves"
      v-slot="{ isHovering, props }"
    >
      <v-card
        v-bind="props"
        class="bg-toplayer transform-scale"
        :class="{
          'on-hover': isHovering,
          'border-selected': selectedSaves.some((s) => s.id === save.id),
        }"
        :elevation="isHovering ? 20 : 3"
        width="250px"
        @click="(e) => onCardClick(save, e)"
      >
        <v-card-text
          class="d-flex flex-column justify-end h-100"
          style="padding: 1.5rem"
        >
          <v-row class="position-relative">
            <v-img
              cover
              height="100%"
              :src="
                save.screenshot?.download_path ??
                getEmptyCoverImage(save.file_name)
              "
            />
            <v-btn-group
              v-if="isHovering"
              class="position-absolute bottom-0 right-0"
              density="compact"
            >
              <v-btn drawer :href="save.download_path" download size="small">
                <v-icon>mdi-download</v-icon>
              </v-btn>
              <v-btn
                v-if="scopes.includes('assets.write')"
                drawer
                size="small"
                @click="
                  emitter?.emit('showDeleteSavesDialog', {
                    rom: props.rom,
                    saves: [save],
                  })
                "
              >
                <v-icon class="text-romm-red">mdi-delete</v-icon>
              </v-btn>
            </v-btn-group>
          </v-row>
          <v-row class="mt-6 flex-grow-0">{{ save.file_name }}</v-row>
          <v-row
            class="mt-6 d-flex flex-md-wrap ga-2 flex-grow-0"
            style="min-height: 20px"
          >
            <v-chip v-if="save.emulator" size="x-small" color="orange" label>
              {{ save.emulator }}
            </v-chip>
            <v-chip size="x-small" label>
              {{ formatBytes(save.file_size_bytes) }}
            </v-chip>
            <v-chip size="x-small" label>
              {{ formatTimestamp(save.updated_at) }}
            </v-chip>
          </v-row>
        </v-card-text>
      </v-card>
    </v-hover>
    <div v-else>
      <v-col class="text-center mt-6">
        <v-icon size="x-large">mdi-help-rhombus-outline</v-icon>
        <p class="text-h4 mt-2">{{ t("rom.no-saves-found") }}</p>
      </v-col>
    </div>
  </div>
</template>
