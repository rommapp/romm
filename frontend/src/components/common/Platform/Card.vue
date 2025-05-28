<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import type { Platform } from "@/stores/platforms";
import { ROUTES } from "@/plugins/router";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import VanillaTilt from "vanilla-tilt";
import { useDisplay } from "vuetify";

const props = withDefaults(
  defineProps<{ platform: Platform; enable3DTilt?: boolean }>(),
  { enable3DTilt: false },
);
const { smAndDown } = useDisplay();
// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}
const emit = defineEmits(["hover"]);

const tiltCard = ref<TiltHTMLElement | null>(null);

onMounted(() => {
  if (tiltCard.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCard.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCard.value?.vanillaTilt && props.enable3DTilt) {
    tiltCard.value.vanillaTilt.destroy();
  }
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <div data-tilt ref="tiltCard">
      <v-card
        v-bind="props"
        class="bg-toplayer"
        :class="{ 'on-hover': isHovering, 'transform-scale': !enable3DTilt }"
        :elevation="isHovering ? 20 : 3"
        :aria-label="`${platform.name} platform card`"
        :to="{ name: ROUTES.PLATFORM, params: { platform: platform.id } }"
        @mouseenter="
          () => {
            emit('hover', { isHovering: true, id: platform.id });
          }
        "
        @mouseleave="
          () => {
            emit('hover', { isHovering: false, id: platform.id });
          }
        "
      >
        <v-card-text>
          <v-row class="pa-1 justify-center bg-background">
            <div
              :title="platform.display_name"
              class="px-2 text-truncate text-caption"
            >
              <span>{{ platform.display_name }}</span>
            </div>
          </v-row>
          <v-row class="pa-1 justify-center">
            <platform-icon
              :key="platform.slug"
              :slug="platform.slug"
              :name="platform.name"
              :fs-slug="platform.fs_slug"
              :size="105"
              class="mt-2"
            />
            <v-chip
              class="bg-background position-absolute"
              size="x-small"
              style="bottom: 1rem; right: 1rem"
              label
            >
              {{ platform.rom_count }}
            </v-chip>
          </v-row>
        </v-card-text>
      </v-card>
    </div>
  </v-hover>
</template>
