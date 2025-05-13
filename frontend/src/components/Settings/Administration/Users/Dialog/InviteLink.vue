<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { lgAndUp } = useDisplay();
const show = ref(false);
const fullInviteLink = ref("");

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateInviteLinkDialog", (token) => {
  fullInviteLink.value = `${window.location.origin}/register?token=${token}`;
  show.value = true;
});

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-share"
    :width="lgAndUp ? '60vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center text-center pa-2 mb-3" no-gutters>
        <v-list-item class="bg-toplayer">{{ fullInviteLink }}</v-list-item>
      </v-row>
    </template>
  </r-dialog>
</template>
