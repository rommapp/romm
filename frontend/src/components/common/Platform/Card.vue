<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import { useRouter } from "vue-router";
const router = useRouter();
const props = defineProps<{ platform: Platform }>();

const onClick = (event: MouseEvent) => {
  if (event.metaKey || event.ctrlKey) {
    const link = router.resolve({
      name: "platform",
      params: { platform: props.platform.id },
    });
    window.open(link.href, "_blank");
  } else {
    router.push({ name: "platform", params: { platform: props.platform.id } });
  }
};
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      :class="{ 'on-hover': isHovering }"
      class="bg-terciary transform-scale"
      :elevation="isHovering ? 20 : 3"
      @click="onClick"
    >
      <v-card-text>
        <v-row class="pa-1 justify-center bg-primary">
          <div
            :title="platform.name?.toString()"
            class="px-2 text-truncate text-caption"
          >
            <span>{{ platform.name }}</span>
          </div>
        </v-row>
        <v-row class="pa-1 justify-center">
          <platform-icon
            :key="platform.slug"
            :slug="platform.slug"
            :name="platform.name"
            :size="105"
            class="mt-2"
          />
          <v-chip
            class="bg-chip position-absolute"
            size="x-small"
            style="bottom: 1rem; right: 1rem"
            label
          >
            {{ platform.rom_count }}
          </v-chip>
        </v-row>
      </v-card-text>
    </v-card>
  </v-hover>
</template>
