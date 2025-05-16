<script setup lang="ts">
import EmptySaves from "@/components/common/EmptyStates/EmptySaves.vue";
import type { SaveSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
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
  <v-row class="ma-2" no-gutters>
    <v-col class="pa-1">
      <v-btn-group divided density="default">
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
          size="small"
          @click="emitter?.emit('addSavesDialog', rom)"
        >
          <v-icon>mdi-cloud-upload-outline</v-icon>
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
    </v-col>
  </v-row>
  <v-row v-if="rom.user_saves.length > 0" class="ma-2" no-gutters>
    <v-col cols="6" sm="4" class="pa-1" v-for="save in rom.user_saves">
      <v-hover v-slot="{ isHovering, props }">
        <v-card
          v-bind="props"
          class="bg-toplayer transform-scale"
          :class="{
            'on-hover': isHovering,
            'border-selected': selectedSaves.some((s) => s.id === save.id),
          }"
          :elevation="isHovering ? 20 : 3"
          @click="(e) => onCardClick(save, e)"
        >
          <v-card-text class="pa-2">
            <v-row no-gutters>
              <v-col cols="12">
                <v-img
                  rounded
                  :src="
                    save.screenshot?.download_path ??
                    getEmptyCoverImage(save.file_name)
                  "
                >
                  <v-slide-x-transition>
                    <v-btn-group
                      v-if="isHovering"
                      class="position-absolute"
                      density="compact"
                      style="bottom: 4px; right: 4px"
                    >
                      <v-btn
                        drawer
                        :href="save.download_path"
                        download
                        size="small"
                      >
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
                  </v-slide-x-transition>
                </v-img>
              </v-col>
            </v-row>
            <v-row class="py-2 text-caption" no-gutters>{{
              save.file_name
            }}</v-row>
            <v-row class="ga-1" no-gutters>
              <v-col v-if="save.emulator" cols="12">
                <v-chip size="x-small" color="orange" label>
                  {{ save.emulator }}
                </v-chip>
              </v-col>
              <v-col cols="12">
                <v-chip size="x-small" label>
                  {{ formatBytes(save.file_size_bytes) }}
                </v-chip>
              </v-col>
              <v-col cols="12">
                <v-chip size="x-small" label>
                  Updated: {{ formatTimestamp(save.updated_at) }}
                </v-chip>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-hover>
    </v-col>
  </v-row>
  <empty-saves v-else />
</template>
