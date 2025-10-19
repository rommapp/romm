<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { Events } from "@/types/emitter";

withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);

const { t } = useI18n();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");

async function goToRandomGame() {
  try {
    const apiParams = {
      limit: 1,
      offset: 0,
    };

    // Get the total count first
    const { data: romsResponse } = await romApi.getRoms(apiParams);

    if (!romsResponse.total || romsResponse.total === 0) {
      emitter?.emit("snackbarShow", {
        msg: "No games found",
        icon: "mdi-information",
        color: "info",
        timeout: 3000,
      });
      return;
    }

    // Get a random offset between 0 and total-1
    const randomOffset = Math.floor(Math.random() * romsResponse.total);
    const { data: randomRomResponse } = await romApi.getRoms({
      ...apiParams,
      offset: randomOffset,
    });

    if (randomRomResponse.items.length > 0) {
      const randomRom = randomRomResponse.items[0];
      router.push({ name: ROUTES.ROM, params: { rom: randomRom.id } });
    } else {
      emitter?.emit("snackbarShow", {
        msg: "Could not find a random game",
        icon: "mdi-alert",
        color: "warning",
        timeout: 3000,
      });
    }
  } catch (error) {
    console.error("Error fetching random game:", error);
    emitter?.emit("snackbarShow", {
      msg: "Error finding random game",
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  }
}
</script>

<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="bg-background d-flex align-center justify-center"
    @click="goToRandomGame"
  >
    <div class="d-flex flex-column align-center">
      <v-icon>mdi-shuffle-variant</v-icon>
      <v-expand-transition>
        <span v-if="withTag" class="text-caption text-center">{{
          t("common.random")
        }}</span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>
