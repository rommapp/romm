<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storeHeartbeat from "@/stores/heartbeat";
import api from "@/services/api";

// Props
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const platformBindingToDelete = ref();
emitter?.on("showDeletePlatformBindingDialog", (fsSlug: string) => {
  platformBindingToDelete.value = fsSlug;
  show.value = true;
});

// Functions
function removeBindPlatform() {
  api.removePlatformBindConfig({ fsSlug: platformBindingToDelete.value });
  heartbeat.removePlatformBinding(platformBindingToDelete.value);
  show.value = false;
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <v-dialog
    v-model="show"
    width="auto"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
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
          <span class="mr-1">Deleting platform binding</span
          ><span class="text-romm-accent-1"
            ><span class="text-romm-accent-1">{{
              platformBindingToDelete
            }}</span></span
          >.
          <span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn
            @click="removeBindPlatform()"
            class="text-romm-red bg-terciary ml-5"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
