<script setup>
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";

// Props
const props = defineProps(["platform", "rail"]);
</script>

<template>
  <v-list-item
    :to="`/platform/${platform.slug}`"
    :value="platform.slug"
    :key="platform"
    class="pt-4 pb-4 bg-terciary"
  >
    <span v-if="!rail" class="text-body-2">{{ platform.name }}</span>
    <template v-slot:prepend>
      <v-avatar :rounded="0" size="40">
        <platform-icon :platform="platform.slug"></platform-icon>
        <div class="igdb-icon" v-if="!platform.igdb_id" title="Not found in IGDB">
          ⚠️
        </div>
      </v-avatar>
    </template>
    <template v-slot:append>
      <v-chip v-if="!rail" class="ml-4 bg-chip" size="x-small" label>
        {{ platform.rom_count }}
      </v-chip>
    </template>
  </v-list-item>
</template>

<style scoped>
.igdb-icon {
  position: absolute;
  bottom: 0;
  right: 0;
}
</style>
