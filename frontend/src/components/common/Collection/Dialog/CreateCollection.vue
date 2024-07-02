<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RDialog from "@/components/common/RDialog.vue";
import collectionApi, {
  type UpdateCollection,
} from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { smAndDown, mdAndUp } = useDisplay();
const show = ref(false);
const collection = ref<UpdateCollection>({
  name: "",
  description: "",
} as UpdateCollection);
const collectionsStore = storeCollections();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateCollectionDialog", () => {
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
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`;
  removeCover.value = true;
}

async function createCollection() {
  if (!collection.value) return;

  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await collectionApi
    .createCollection({
      name: collection.value.name,
      description: collection.value.description,
    })
    .then(({ data }) => {
      collectionsStore.add(data);
      emitter?.emit("snackbarShow", {
        msg: `Collection ${data.name} created successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
      show.value = false;
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
    });
}

function closeDialog() {
  show.value = false;
  collection.value = {
    name: "",
    description: "",
  } as UpdateCollection;
  imagePreviewUrl.value = "";
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-bookmark-box-multiple"
    :width="mdAndUp ? '55vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" md="8" lg="8" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="collection.name"
                label="Name"
                variant="outlined"
                required
                hide-details
                @keyup.enter="createCollection()"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-textarea
                v-model="collection.description"
                class="mt-1"
                label="Description"
                variant="outlined"
                required
                hide-details
                @keyup.enter="createCollection()"
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
      <v-row class="justify-center MT-4 mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :disabled="!collection.name"
            :variant="!collection.name ? 'plain' : 'flat'"
            @click="createCollection"
          >
            Create
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
