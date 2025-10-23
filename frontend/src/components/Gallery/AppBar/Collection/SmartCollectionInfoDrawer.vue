<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import CollectionCard from "@/components/common/Collection/Card.vue";
import DeleteCollectionDialog from "@/components/common/Collection/Dialog/DeleteCollection.vue";
import RSection from "@/components/common/RSection.vue";
import collectionApi from "@/services/api/collection";
import storeAuth from "@/stores/auth";
import storeCollection from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { smAndDown } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const romsStore = storeRoms();
const collectionsStore = storeCollection();
const { currentSmartCollection } = storeToRefs(romsStore);
const navigationStore = storeNavigation();
const { activeCollectionInfoDrawer } = storeToRefs(navigationStore);
const collectionInfoFields = [
  {
    key: "rom_count",
    label: "Roms",
  },
  {
    key: "user__username",
    label: t("collection.owner"),
  },
];
const updating = ref(false);
const isEditable = ref(false);

function showEditable() {
  isEditable.value = true;
}

function closeEditable() {
  isEditable.value = false;
}

async function updateCollection() {
  if (!currentSmartCollection.value) return;
  updating.value = true;
  isEditable.value = !isEditable.value;

  await collectionApi
    .updateSmartCollection({
      smartCollection: currentSmartCollection.value,
    })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Collection updated successfully",
        icon: "mdi-check-bold",
        color: "green",
      });
      currentSmartCollection.value = data;
      collectionsStore.updateSmartCollection(data);
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Failed to update collection: ${
          error.response?.data?.msg || error.message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      updating.value = false;
    });
}
</script>

<template>
  <v-navigation-drawer
    v-if="currentSmartCollection"
    v-model="activeCollectionInfoDrawer"
    mobile
    floating
    width="500"
    :class="{
      'ml-2': activeCollectionInfoDrawer,
      'drawer-mobile': smAndDown && activeCollectionInfoDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-row no-gutters class="justify-center align-center pa-2">
      <v-col style="max-width: 240px" cols="12">
        <div class="text-center justify-center align-center">
          <div class="position-absolute append-top-right mr-5">
            <template
              v-if="
                currentSmartCollection.user__username === auth.user?.username &&
                auth.scopes.includes('collections.write')
              "
            >
              <v-btn
                v-if="!isEditable"
                :loading="updating"
                class="bg-toplayer"
                size="small"
                @click="showEditable"
              >
                <template #loader>
                  <v-progress-circular
                    color="primary"
                    :width="2"
                    :size="20"
                    indeterminate
                  />
                </template>
                <v-icon>mdi-pencil</v-icon>
              </v-btn>
              <template v-else>
                <v-btn size="small" class="bg-toplayer" @click="closeEditable">
                  <v-icon color="romm-red"> mdi-close </v-icon>
                </v-btn>
                <v-btn
                  size="small"
                  class="bg-toplayer ml-1"
                  @click="updateCollection"
                >
                  <v-icon color="romm-green"> mdi-check </v-icon>
                </v-btn>
              </template>
            </template>
          </div>
          <CollectionCard
            :key="currentSmartCollection.updated_at"
            :show-title="false"
            :with-link="false"
            :collection="currentSmartCollection"
          />
        </div>
      </v-col>
      <v-col cols="12">
        <div class="text-center mt-4">
          <div v-if="!isEditable">
            <div>
              <span class="text-h5 font-weight-bold pl-0">{{
                currentSmartCollection.name
              }}</span>
            </div>
            <div>
              <span class="text-subtitle-2">{{
                currentSmartCollection.description
              }}</span>
            </div>
            <v-chip
              class="mt-4"
              size="small"
              :color="currentSmartCollection.is_public ? 'primary' : ''"
            >
              <v-icon class="mr-1">
                {{
                  currentSmartCollection.is_public
                    ? "mdi-lock-open"
                    : "mdi-lock"
                }} </v-icon
              >{{
                currentSmartCollection.is_public
                  ? t("collection.public")
                  : t("collection.private")
              }}
            </v-chip>
          </div>
          <div v-else class="text-center">
            <v-text-field
              v-model="currentSmartCollection.name"
              class="mt-2"
              :label="t('collection.name')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection"
            />
            <v-text-field
              v-model="currentSmartCollection.description"
              class="mt-4"
              :label="t('collection.description')"
              variant="outlined"
              required
              density="compact"
              hide-details
              @keyup.enter="updateCollection"
            />
            <v-switch
              v-model="currentSmartCollection.is_public"
              class="mt-2"
              color="primary"
              false-icon="mdi-lock"
              true-icon="mdi-lock-open"
              inset
              hide-details
              :label="
                currentSmartCollection.is_public
                  ? t('collection.public-desc')
                  : t('collection.private-desc')
              "
            />
          </div>
        </div>
      </v-col>
      <v-col cols="12">
        <v-card class="mt-4 bg-toplayer fill-width" elevation="0">
          <v-card-text class="pa-4 d-flex">
            <template v-for="field in collectionInfoFields" :key="field.key">
              <div>
                <v-chip size="small" class="mr-2 px-0" label>
                  <v-chip label>{{ field.label }}</v-chip>
                  <span class="px-2">{{
                    currentSmartCollection[
                      field.key as keyof typeof currentSmartCollection
                    ]?.toString()
                      ? currentSmartCollection[
                          field.key as keyof typeof currentSmartCollection
                        ]
                      : "N/A"
                  }}</span>
                </v-chip>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12">
        <v-card class="mt-4 bg-toplayer fill-width" elevation="0">
          <v-card-text class="pa-4 d-flex">
            <template
              v-for="filter in Object.entries(
                currentSmartCollection.filter_criteria,
              )"
              :key="filter[0]"
            >
              <div>
                <v-chip size="small" class="mr-2 px-0" label>
                  <v-chip label> {{ filter[0] }} </v-chip>
                  <span class="px-2">{{ filter[1] }}</span>
                </v-chip>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <RSection
      v-if="
        auth.scopes.includes('collections.write') &&
        currentSmartCollection.user__username === auth.user?.username
      "
      icon="mdi-alert"
      icon-color="red"
      :title="t('collection.danger-zone')"
      elevation="0"
      title-divider
      bg-color="bg-toplayer"
      class="mx-2"
    >
      <template #content>
        <div class="text-center">
          <v-btn
            class="text-romm-red bg-toplayer ma-2"
            variant="flat"
            @click="
              emitter?.emit(
                'showDeleteSmartCollectionDialog',
                currentSmartCollection,
              )
            "
          >
            <v-icon class="text-romm-red mr-2"> mdi-delete </v-icon>
            {{ t("collection.delete-collection") }}
          </v-btn>
        </div>
      </template>
    </RSection>
  </v-navigation-drawer>

  <DeleteCollectionDialog />
</template>
<style scoped>
.append-top-right {
  top: 0.3rem;
  right: 0.3rem;
  z-index: 1;
}
</style>
