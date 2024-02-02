<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import { regionToEmoji, languageToEmoji } from "@/utils";
import type { RomSchema, PlatformSchema } from "@/__generated__/";
import { useDisplay } from "vuetify";

defineProps<{ rom: RomSchema; platform: PlatformSchema }>();
const { smAndDown } = useDisplay();
</script>
<template>
  <v-row
    class="text-white text-shadow text-h5 font-weight-bold"
    :class="{ 'text-center': smAndDown }"
    no-gutters
  >
    <v-col cols="12">
      <span>{{ rom.name }}</span>
    </v-col>
    <v-col cols="12">
      <v-chip
        class="my-2 pl-4"
        :to="{ name: 'platform', params: { platform: platform.id } }"
      >
        {{ platform.name }}
        <v-avatar :rounded="0" size="40" class="ml-2 py-2">
          <platform-icon :key="platform.slug" :slug="platform.slug" />
        </v-avatar>
      </v-chip>
      <v-chip
        class="ml-2 my-2"
        v-if="rom.regions.filter((i: string) => i).length > 0"
        :title="`Regions: ${rom.regions.join(', ')}`"
      >
        <span class="px-1" v-for="region in rom.regions">{{
          regionToEmoji(region)
        }}</span>
      </v-chip>
      <v-chip
        class="ml-2 my-2"
        v-if="rom.languages.filter((i: string) => i).length > 0"
        :title="`Languages: ${rom.languages.join(', ')}`"
      >
        <span class="px-1" v-for="language in rom.languages">{{
          languageToEmoji(language)
        }}</span>
      </v-chip>
      <v-chip v-show="rom.revision" class="ml-2 my-2"
        >Revision {{ rom.revision }}
      </v-chip>
    </v-col>
    <v-col cols="12">
      <v-chip size="x-small" class="justify-center align-center">
        <span>IGDB</span>
        <v-divider class="ma-2 border-opacity-25" vertical />
        <a
          style="text-decoration: none; color: inherit"
          :href="`https://www.igdb.com/games/${rom.slug}`"
          target="_blank"
          >ID: {{ rom.igdb_id }}</a
        >
        <v-divider class="ma-2 border-opacity-25" vertical />
        <span>Rating: {{ rom.total_rating }}</span>
      </v-chip>
    </v-col>
  </v-row>
</template>

<style scoped>
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
