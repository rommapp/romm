<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import type { Events } from "@/types/emitter";
import { getRoleIcon } from "@/utils";
import userApi from "@/services/api/user";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { lgAndUp } = useDisplay();
const show = ref(false);
const fullInviteLink = ref("");
const selectedRole = ref("");
const roles = ["viewer", "editor", "admin"];
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateInviteLinkDialog", () => {
  show.value = true;
});

function createInviteLink() {
  userApi
    .createInviteLink({ role: selectedRole.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Invite link created",
        icon: "mdi-check-circle",
        color: "green",
        timeout: 5000,
      });
      fullInviteLink.value = `${window.location.origin}/register?token=${data.token}`;
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to create invite link: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });
}

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
      <v-row class="justify-center text-center pa-2" no-gutters>
        <v-btn-toggle class="ma-1" divided v-model="selectedRole">
          <v-btn
            v-for="role in roles"
            :key="role"
            variant="outlined"
            :value="role"
          >
            <v-icon size="small" class="mr-2">{{ getRoleIcon(role) }}</v-icon
            >{{ role.charAt(0).toUpperCase() + role.slice(1) }}
          </v-btn>
        </v-btn-toggle>
        <v-btn-toggle class="text-primary ma-1" divided>
          <v-btn
            :disabled="!selectedRole"
            variant="outlined"
            @click="createInviteLink"
          >
            <v-icon size="small" class="mr-2">mdi-link</v-icon>Generate
          </v-btn>
        </v-btn-toggle>
      </v-row>
      <v-row v-show="fullInviteLink" class="text-center pa-2" no-gutters>
        <v-list-item rounded class="bg-toplayer py-2">{{
          fullInviteLink
        }}</v-list-item>
      </v-row>
    </template>
  </r-dialog>
</template>
