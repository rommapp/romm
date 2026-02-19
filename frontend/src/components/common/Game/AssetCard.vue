<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp, formatRelativeDate } from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";

const { t, locale } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");

export type AssetType = "save" | "state";

const props = withDefaults(
  defineProps<{
    asset: SaveSchema | StateSchema;
    type: AssetType;
    selected?: boolean;
    rom?: DetailedRom;
    showHoverActions?: boolean;
    showCloseButton?: boolean;
    scopes?: string[];
    cardStyle?: Record<string, any>;
    transformScale?: boolean;
  }>(),
  {
    selected: false,
    showHoverActions: true,
    showCloseButton: false,
    scopes: () => [],
    cardStyle: () => ({}),
    transformScale: true,
  },
);

const emit = defineEmits<{
  (e: "click", event: MouseEvent): void;
  (e: "close"): void;
}>();

function isState(asset: SaveSchema | StateSchema): asset is StateSchema {
  return "screenshot" in asset;
}

function handleClick(event: MouseEvent) {
  emit("click", event);
}

function handleClose() {
  emit("close");
}

function handleDelete(event: Event) {
  event.stopPropagation();
  if (!props.rom) {
    return;
  }
  if (props.type === "save") {
    emitter?.emit("showDeleteSavesDialog", {
      rom: props.rom,
      saves: [props.asset as SaveSchema],
    });
  } else {
    emitter?.emit("showDeleteStatesDialog", {
      rom: props.rom,
      states: [props.asset as StateSchema],
    });
  }
}
</script>

<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-card
      v-bind="hoverProps"
      :style="cardStyle"
      class="bg-toplayer"
      :class="{
        'border-selected': selected,
        'transform-scale': transformScale,
      }"
      @click="handleClick"
    >
      <v-card-text class="pa-2">
        <v-row v-if="asset.screenshot" no-gutters class="bg-surface">
          <v-col cols="12">
            <v-img
              rounded
              :src="
                asset.screenshot?.download_path ??
                getEmptyCoverImage(asset.file_name, 16 / 9)
              "
              :aspect-ratio="16 / 9"
            />
          </v-col>
        </v-row>

        <!-- File name -->
        <v-row class="text-caption py-2 px-1 text-primary" no-gutters>
          {{ asset.file_name }}
        </v-row>

        <!-- Metadata -->
        <v-row class="ga-1 pa-1" no-gutters>
          <v-col cols="12">
            <v-chip
              v-if="asset.emulator"
              size="x-small"
              color="orange"
              class="mr-2"
              label
            >
              {{ asset.emulator }}
            </v-chip>
            <v-chip size="x-small" label>
              {{ formatBytes(asset.file_size_bytes) }}
            </v-chip>
          </v-col>
          <v-col cols="12">
            <div class="mt-2">
              {{ t("rom.updated") }}:
              {{ formatTimestamp(asset.updated_at, locale) }}
            </div>
          </v-col>
          <v-col cols="12">
            <div class="mt-1">
              <span class="text-grey text-caption"
                >({{ formatRelativeDate(asset.updated_at) }})</span
              >
            </div>
          </v-col>
        </v-row>

        <!-- Action buttons -->
        <v-slide-x-transition>
          <v-btn-group
            v-if="isHovering && showHoverActions"
            class="position-absolute"
            density="compact"
            style="bottom: 4px; right: 4px"
          >
            <v-btn drawer :href="asset.download_path" download size="small">
              <v-icon>mdi-download</v-icon>
            </v-btn>
            <v-btn
              v-if="scopes.includes('assets.write')"
              drawer
              size="small"
              @click="handleDelete"
            >
              <v-icon class="text-romm-red">mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </v-slide-x-transition>

        <!-- Close button -->
        <v-btn
          v-if="showCloseButton"
          variant="text"
          size="small"
          class="position-absolute"
          style="bottom: 8px; right: 8px"
          @click.stop="handleClose"
        >
          <v-icon>mdi-close-circle-outline</v-icon>
        </v-btn>
      </v-card-text>
    </v-card>
  </v-hover>
</template>
