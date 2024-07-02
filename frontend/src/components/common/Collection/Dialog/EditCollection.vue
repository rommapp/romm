<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi from "@/services/api/collection";
import type { UpdateCollection } from "@/services/api/collection";
import { type Collection } from "@/stores/collections";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { smAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const collection = ref<UpdateCollection>();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditCollectionDialog", (collectionToEdit: Collection) => {
  collection.value = collectionToEdit;
  show.value = true;
});

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;

  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
}

async function removeArtwork() {
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_collection.png`;
  removeCover.value = true;
}

async function editCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await collectionApi
    .updateCollection({
      collection: collection.value,
    })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: `Collection updated successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      closeDialog();
    });
}

function closeDialog() {
  show.value = false;
  collection.value = undefined;
  imagePreviewUrl.value = "";
}
</script>

<template>
  <r-dialog
    v-if="collection"
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    :width="lgAndUp ? '65vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" md="8" lg="8" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.name"
                class="py-2"
                label="Name"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-textarea
                v-model="collection.description"
                class="py-2"
                label="Description"
                variant="outlined"
                required
                hide-details
                @keyup.enter="editCollection"
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col>
          <v-row class="pa-2 justify-center" no-gutters>
            <v-col class="cover">
              <collection-card
                :show-title="false"
                :with-link="false"
                :collection="collection"
                :src="imagePreviewUrl"
              >
                <template #append-inner>
                  <v-chip-group class="pa-0">
                    <v-chip
                      class="translucent-dark"
                      :size="smAndDown ? 'large' : 'small'"
                      @click="triggerFileInput"
                      label
                    >
                      <v-icon>mdi-pencil</v-icon>
                      <v-file-input
                        id="file-input"
                        v-model="collection.artwork"
                        accept="image/*"
                        hide-details
                        class="file-input"
                        @change="previewImage"
                      />
                    </v-chip>
                    <v-chip
                      class="translucent-dark"
                      :size="smAndDown ? 'large' : 'small'"
                      @click="removeArtwork"
                      label
                    >
                      <v-icon class="text-romm-red"> mdi-delete </v-icon>
                    </v-chip>
                  </v-chip-group>
                </template>
              </collection-card>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mt-4 mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="text-romm-green bg-terciary" @click="editCollection">
            Update
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
<style scoped>
.cover {
  min-width: 240px;
  min-height: 330px;
  max-width: 240px;
  max-height: 330px;
}
</style>
