<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity } from "lodash";
import { useDisplay } from "vuetify";

defineProps<{ rom: DetailedRom; platform: Platform }>();
const { smAndDown } = useDisplay();
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
        class="font-italic ml-2"
        size="x-small"
        v-if="Number(rom.first_release_date) > 0"
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
    class="text-white text-shadow mb-2"
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
      <v-chip
        size="small"
        class="mr-1 my-2"
        v-if="rom.regions.filter(identity).length > 0"
        :title="`Regions: ${rom.regions.join(', ')}`"
      >
        <span class="px-1" v-for="region in rom.regions">{{
          regionToEmoji(region)
        }}</span>
      </v-chip>
      <v-chip
        size="small"
        class="mr-1 my-2"
        v-if="rom.languages.filter(identity).length > 0"
        :title="`Languages: ${rom.languages.join(', ')}`"
      >
        <span class="px-1" v-for="language in rom.languages">{{
          languageToEmoji(language)
        }}</span>
      </v-chip>
      <v-chip size="small" v-if="rom.revision" class="my-2"
        >Revision {{ rom.revision }}
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
        <v-chip size="x-small" @click="">
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
        <v-chip size="x-small" @click="">
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
