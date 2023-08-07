<script setup>
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { deleteRomApi } from "@/services/api.js";

const router = useRouter();
const deleteFromFs = ref(false);
const { xs, mdAndDown, lgAndUp } = useDisplay();
const props = defineProps(["show", "rom"]);
const emitter = inject("emitter");

async function deleteRom() {
  await deleteRomApi(props.rom, deleteFromFs.value)
    .then((response) => {
      emitter.emit("refreshPlatforms");
      emitter.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      router.push(`/platform/${props.rom.p_slug}`);
    })
    .catch((error) => {
      console.log(error);
      emitter.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      if (error.response.status == 404) {
        router.push(`/platform/${props.rom.p_slug}`);
      }
    });
  emitter.emit("close-delete-dialog");
}
</script>

<template>
  <v-dialog
    :modelValue="show"
    width="auto"
    @click:outside="emitter.emit('close-delete-dialog')"
  >
    <v-card
      rounded="0"
      :class="{
        'delete-content': lgAndUp,
        'delete-content-tablet': mdAndDown,
        'delete-content-mobile': xs,
      }"
    >
      <v-toolbar density="compact" class="bg-primary">
        <v-row class="align-center" no-gutters>
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-delete" class="ml-5" />
          </v-col>
          <v-col>
            <v-btn
              @click="emitter.emit('close-delete-dialog')"
              class="bg-primary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text class="bg-secondary">
        <v-row class="justify-center pa-2" no-gutters>
          <span>Deleting {{ rom.file_name }}. Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="emitter.emit('close-delete-dialog')">Cancel</v-btn>
          <v-btn @click="deleteRom()" class="text-red ml-5">Confirm</v-btn>
        </v-row>
      </v-card-text>

      <v-divider class="border-opacity-25" :thickness="1" />
      <v-toolbar class="bg-primary" density="compact">
        <v-checkbox
          v-model="deleteFromFs"
          label="Remove from filesystem"
          class="ml-3"
          hide-details
        />
      </v-toolbar>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.delete-content {
  width: 900px;
}

.delete-content-tablet {
  width: 570px;
}

.delete-content-mobile {
  width: 85vw;
}
</style>
