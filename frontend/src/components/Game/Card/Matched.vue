<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import Sources from "@/components/Game/Card/Sources.vue";
import { useTheme } from "vuetify";

// Props
const props = defineProps<{
  rom: SearchRomSchema;
}>();
const emit = defineEmits(["click"]);
const handleClick = (event: MouseEvent) => {
  emit("click", { event: event, rom: props.rom });
};
const theme = useTheme();
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      class="transform-scale"
      :class="{
        'on-hover': isHovering,
      }"
      :elevation="isHovering ? 20 : 2"
    >
      <v-hover v-slot="{ isHovering, props }" open-delay="800">
        <v-img
          @click="handleClick"
          v-bind="props"
          class="pointer"
          ref="card"
          :src="
            !rom.igdb_url_cover && !rom.moby_url_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : rom.igdb_url_cover
              ? rom.igdb_url_cover
              : rom.moby_url_cover
          "
          :aspect-ratio="3 / 4"
        >
          <div v-bind="props" style="position: absolute; top: 0; width: 100%">
            <v-expand-transition>
              <div
                v-if="
                  isHovering || (!rom.igdb_url_cover && !rom.moby_url_cover)
                "
                class="translucent text-caption"
              >
                <v-list-item>{{ rom.name }}</v-list-item>
              </div>
            </v-expand-transition>

            <sources :rom="rom" />
            <slot name="prepend-inner"></slot>
          </div>
          <div class="position-absolute append-inner">
            <slot name="append-inner"></slot>
          </div>

          <template #error>
            <v-img
              :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
              :aspect-ratio="3 / 4"
            ></v-img>
          </template>
          <template #placeholder>
            <div class="d-flex align-center justify-center fill-height">
              <v-progress-circular
                :width="2"
                :size="40"
                color="romm-accent-1"
                indeterminate
              />
            </div>
          </template>
        </v-img>
      </v-hover>
      <v-card-text>
        <v-row class="pa-1 align-center">
          <v-col class="pa-0 ml-1 text-truncate">
            <span>{{ rom.name }}</span>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-hover>
</template>

<style scoped>
.v-card.with-border {
  border: 3px solid rgba(var(--v-theme-primary));
}
.v-card.selected {
  border: 3px solid rgba(var(--v-theme-romm-accent-1));
  transform: scale(1.03);
}
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: max-height 0.5s; /* Add a transition for a smooth effect */
}
.expand-on-hover:hover {
  max-height: 1000px; /* Adjust to a sufficiently large value to ensure the full expansion */
}
/* Apply styles to v-expand-transition component */
.v-expand-transition-enter-active,
.v-expand-transition-leave-active {
  transition: max-height 0.5s; /* Adjust the transition duration if needed */
}
.v-expand-transition-enter, .v-expand-transition-leave-to /* .v-expand-transition-leave-active in <2.1.8 */ {
  max-height: 0; /* Set max-height to 0 when entering or leaving */
  overflow: hidden;
}
.v-img {
  user-select: none; /* Prevents text selection */
  -webkit-user-select: none; /* Safari */
  -moz-user-select: none; /* Firefox */
  -ms-user-select: none; /* Internet Explorer/Edge */
}
.append-inner {
  bottom: -0.1rem;
  right: -0.3rem;
}
</style>
