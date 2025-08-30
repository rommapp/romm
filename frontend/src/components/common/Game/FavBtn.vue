<script setup lang="ts">
import storeCollections from "@/stores/collections";
import { type SimpleRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useFavoriteToggle } from "@/composables/useFavoriteToggle";

const props = defineProps<{ rom: SimpleRom }>();
const collectionsStore = storeCollections();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const { toggleFavorite } = useFavoriteToggle(emitter);

async function switchFromFavourites() {
  await toggleFavorite(props.rom);
}
</script>

<template>
  <v-btn
    v-if="auth.scopes.includes('roms.user.write')"
    class="translucent text-shadow"
    rouded="0"
    size="small"
    variant="text"
    @click.stop="switchFromFavourites"
  >
    <v-icon color="primary">
      {{ collectionsStore.isFavorite(rom) ? "mdi-star" : "mdi-star-outline" }}
    </v-icon>
  </v-btn>
</template>
