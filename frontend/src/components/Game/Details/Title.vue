<script setup lang="ts">
import PlatformIcon from "@/components/Platform/Icon.vue";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity } from "lodash";
import { useDisplay } from "vuetify";

defineProps<{ rom: DetailedRom; platform: Platform }>();
const { xs, smAndDown } = useDisplay();
</script>
<template>
  <v-row
    class="text-white text-shadow mb-2"
    :class="{ 'text-center': smAndDown }"
    no-gutters
  >
    <v-col>
      <span class="text-h5 font-weight-bold px-1 mb-1" variant="text" label>{{
        rom.name
      }}</span>
      <v-chip
        v-if="Number(rom.first_release_date) > 0"
        class="font-italic ml-2"
        size="x-small"
      >
        {{
          new Date(Number(rom.first_release_date) * 1000).toLocaleDateString(
            "en-US",
            {
              day: "2-digit",
              month: "short",
              year: "numeric",
            }
          )
        }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row
  class="text-white text-shadow mb-1"
  :class="{ 'text-center': smAndDown }"
    no-gutters
    >
    <v-col cols="12">
      <v-chip
      class="mr-1"
        :to="{ name: 'platform', params: { platform: platform.id } }"
        >
        {{ platform.name }}
        <v-avatar :rounded="0" size="30" class="ml-2">
          <platform-icon :key="platform.slug" :slug="platform.slug" />
        </v-avatar>
      </v-chip>
      <!-- TODO: refactor this mess + add options to Flags -->
      <!-- TODO: Date to the right side of the platform chip when xs -->
      <v-row no-gutters v-if="xs" class="my-1"><v-col></v-col></v-row>
      <v-chip
        v-if="rom.regions.filter(identity).length > 0"
        size="small"
        :title="`Regions: ${rom.regions.join(', ')}`"
      >
        <span v-for="region in rom.regions" :key="region" class="px-1">{{
          regionToEmoji(region)
        }}</span>
      </v-chip>
      <v-chip
        v-if="rom.languages.filter(identity).length > 0"
        size="small"
        class="ml-1"
        :title="`Languages: ${rom.languages.join(', ')}`"
      >
        <span v-for="language in rom.languages" :key="language" class="px-1">{{
          languageToEmoji(language)
        }}</span>
      </v-chip>
      <v-chip v-if="rom.revision" size="small" class="ml-1">
        Revision {{ rom.revision }}
      </v-chip>
    </v-col>
  </v-row>
  <v-row
    v-if="rom.igdb_id || rom.moby_id"
    class="text-white text-shadow"
    :class="{ 'text-center': smAndDown }"
    no-gutters
  >
    <v-col cols="12">
      <a
        v-if="rom.igdb_id"
        style="text-decoration: none; color: inherit"
        :href="`https://www.igdb.com/games/${rom.slug}`"
        target="_blank"
      >
        <v-chip size="x-small" @click.stop>
          <span>IGDB</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>ID: {{ rom.igdb_id }}</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>Rating: {{ rom.igdb_metadata?.total_rating }}</span>
        </v-chip>
      </a>
      <a
        v-if="rom.moby_id"
        style="text-decoration: none; color: inherit"
        :href="`https://www.mobygames.com/game/${rom.moby_id}`"
        target="_blank"
        :class="{ 'ml-2': rom.igdb_id }"
      >
        <v-chip size="x-small" @click.stop>
          <span>Mobygames</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>ID: {{ rom.moby_id }}</span>
          <v-divider class="mx-2 border-opacity-25" vertical />
          <span>Rating: {{ rom.moby_metadata?.moby_score }}</span>
        </v-chip>
      </a>
    </v-col>
  </v-row>
</template>

<style scoped>
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
