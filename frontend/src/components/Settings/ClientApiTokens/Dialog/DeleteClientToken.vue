<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import type { Events } from "@/types/emitter";

const emit = defineEmits<{ deleted: [id: number] }>();

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const token = ref<ClientTokenSchema | null>(null);
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");

emitter?.on("showDeleteClientTokenDialog", (tokenToDelete) => {
  token.value = tokenToDelete;
  show.value = true;
});

async function deleteToken() {
  if (!token.value) return;

  await clientTokenApi
    .deleteToken(token.value.id)
    .then(() => {
      emit("deleted", token.value!.id);
      emitter?.emit("snackbarShow", {
        msg: t("settings.client-token-deleted"),
        icon: "mdi-check",
        color: "romm-green",
        timeout: 4000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to delete token: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });

  show.value = false;
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <RDialog
    v-if="token"
    v-model="show"
    icon="mdi-delete"
    :width="lgAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-row class="justify-center align-center pa-4" no-gutters>
        <span>{{ t("settings.client-token-confirm-delete") }}</span>
      </v-row>
      <v-row class="justify-center pa-2" no-gutters>
        <v-chip label class="text-primary">{{ token.name }}</v-chip>
      </v-row>
    </template>
    <template #footer>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-toplayer text-romm-red" @click="deleteToken">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
