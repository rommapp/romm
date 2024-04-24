<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const link = ref("");

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCopyDownloadLinkDialog", (downloadLink) => {
  show.value = true;
  link.value = downloadLink;
});

function closeDialog() {
  show.value = false;
  link.value = "";
}
</script>

<template>
  <v-dialog
    :modelValue="show"
    width="auto"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
  >
    <v-card
      rounded="0"
      :class="{
        'delete-content': lgAndUp,
        'delete-content-tablet': mdAndDown,
        'delete-content-mobile': xs,
      }"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-delete" class="ml-5" />
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />
      <v-card-text>
        <v-row class="justify-center pa-2" no-gutters>
          <span class="text-romm-accent-1 mx-1">{{ link }}</span>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.delete-content {
  width: 900px;
  max-height: 600px;
}

.delete-content-tablet {
  width: 570px;
  max-height: 600px;
}

.delete-content-mobile {
  width: 85vw;
  max-height: 600px;
}
.scroll {
  overflow-y: scroll;
}
</style>
