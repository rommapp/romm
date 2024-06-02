<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const show = ref(false);
const sources = ref<any>([]);
const theme = useTheme();
const { xs } = useDisplay();
const emit = defineEmits(["select:source"]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showSelectSourceDialog", (matchedRom: SearchRomSchema) => {
  sources.value.push({
    url_cover: matchedRom.igdb_url_cover,
    name: "igdb",
    rom: matchedRom,
  });
  sources.value.push({
    url_cover: matchedRom.moby_url_cover,
    name: "moby",
    rom: matchedRom,
  });
  show.value = true;
});

// Functions
function selectSource(matchedRom: SearchRomSchema, source: string) {
  if (source == "igdb") {
    emit(
      "select:source",
      Object.assign(matchedRom, { url_cover: matchedRom.igdb_url_cover })
    );
  } else if (source == "moby") {
    emit(
      "select:source",
      Object.assign(matchedRom, { url_cover: matchedRom.moby_url_cover })
    );
  }
  closeDialog();
}

function closeDialog() {
  show.value = false;
  sources.value = [];
}
</script>

<template>
  <v-dialog
    @update:model-value="closeDialog()"
    :modelValue="show"
    scrim="true"
    scroll-strategy="none"
    width="auto"
  >
    <v-row class="justify-center" no-gutters>
      <v-col
        class="pa-2"
        :class="{ cover: !xs, 'cover-xs': xs }"
        v-for="source in sources"
      >
        <v-hover v-slot="{ isHovering, props }">
          <v-card
            @click="selectSource(source.rom, source.name)"
            v-bind="props"
            class="matched-rom"
            :class="{ 'on-hover': isHovering }"
            :elevation="isHovering ? 20 : 3"
          >
            <v-img
              :src="
                !source.url_cover
                  ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                  : source.url_cover
              "
              :aspect-ratio="3 / 4"
              lazy
            >
              <template #placeholder>
                <div class="d-flex align-center justify-center fill-height">
                  <v-progress-circular
                    color="romm-accent-1"
                    :width="2"
                    indeterminate
                  />
                </div>
              </template>
              <v-row no-gutters class="text-white pa-1">
                <v-tooltip
                  location="top"
                  class="tooltip"
                  transition="fade-transition"
                  text="IGDB matched"
                  open-delay="500"
                  ><template #activator="{ props }">
                    <v-avatar
                      v-bind="props"
                      v-if="source.name == 'igdb'"
                      class="mr-1"
                      size="30"
                      rounded="1"
                    >
                      <v-img
                        src="/assets/scrappers/igdb.png"
                      /> </v-avatar></template
                ></v-tooltip>
                <v-tooltip
                  location="top"
                  class="tooltip"
                  transition="fade-transition"
                  text="Mobygames matched"
                  open-delay="500"
                  ><template #activator="{ props }">
                    <v-avatar
                      v-bind="props"
                      v-if="source.name == 'moby'"
                      class="mr-1"
                      size="30"
                      rounded="1"
                    >
                      <v-img
                        src="/assets/scrappers/moby.png"
                      /> </v-avatar></template
                ></v-tooltip>
              </v-row>
            </v-img>
          </v-card>
        </v-hover>
      </v-col>
    </v-row>
  </v-dialog>
</template>
<style scoped>
.cover {
  min-width: 270px;
  max-width: 270px;
}
.cover-xs {
  min-width: 180px;
  max-width: 180px;
}
.matched-rom {
  transition-property: all;
  transition-duration: 0.1s;
}
.matched-rom.on-hover {
  z-index: 1 !important;
  transform: scale(1.05);
}
</style>
