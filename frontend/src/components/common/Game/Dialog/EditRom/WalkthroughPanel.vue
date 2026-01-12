<script setup lang="ts">
import { ref } from "vue";
import { useDisplay } from "vuetify";
import { useUploadWalkthrough } from "@/composables/useUploadWalkthrough";
import { type StoredWalkthrough } from "@/services/api/walkthrough";

const props = defineProps<{
  romId: number;
  initialWalkthroughs?: StoredWalkthrough[];
}>();

const {
  url,
  loading,
  walkthroughs,
  uploadFile,
  uploading,
  removingId,
  runFetch,
  uploadFileToRom,
  removeSavedWalkthrough,
} = useUploadWalkthrough(props);
const savedOpenPanels = ref<number[]>([]);
const { mdAndUp } = useDisplay();
</script>

<template>
  <v-expansion-panel elevation="0">
    <v-expansion-panel-title class="bg-toplayer">
      <v-icon class="mr-2"> mdi-file-document-outline </v-icon>
      Walkthrough
    </v-expansion-panel-title>
    <v-expansion-panel-text class="mt-4 px-2">
      <v-row no-gutters :class="{ 'flex-column': !mdAndUp }">
        <v-col class="pa-2" :cols="mdAndUp ? 10 : 12">
          <v-text-field
            v-model="url"
            label="Walkthrough URL (GameFAQs)"
            placeholder="https://gamefaqs.gamespot.com/.../faqs/..."
            variant="outlined"
            clearable
          />
        </v-col>
        <v-col class="px-2 d-flex align-center" :cols="mdAndUp ? 2 : 12">
          <v-btn
            color="primary"
            class="bg-toplayer"
            variant="flat"
            :loading="loading"
            block
            @click="runFetch"
          >
            Add Walkthrough
          </v-btn>
        </v-col>
      </v-row>

      <div class="w-full d-flex mb-4">
        <v-divider class="my-2" />
        <span class="mx-4 text-caption text-medium-emphasis"> OR </span>
        <v-divider class="my-2" />
      </div>

      <div class="mb-4">
        <div class="d-flex align-center justify-space-between mb-3">
          <div>
            <div class="text-subtitle-2 font-weight-medium">
              Upload Walkthrough File
            </div>
            <div class="text-caption text-medium-emphasis">
              PDF, HTML, or TXT supported.
            </div>
          </div>
          <v-btn
            color="primary"
            variant="flat"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadFileToRom"
          >
            Upload
          </v-btn>
        </div>
        <v-file-input
          v-model="uploadFile"
          accept=".pdf,.html,.htm,.txt,.md"
          variant="outlined"
          prepend-icon="mdi-file-upload"
          label="Select walkthrough file"
          show-size
        />
      </div>

      <div class="d-flex align-center justify-space-between mb-2">
        <h4 class="text-subtitle-1 font-weight-bold">Saved Walkthroughs</h4>
        <v-chip
          size="small"
          color="primary"
          variant="tonal"
          class="text-caption"
        >
          {{ walkthroughs.length }} saved
        </v-chip>
      </div>

      <v-alert
        v-if="!walkthroughs.length"
        type="info"
        variant="tonal"
        class="my-2"
        text="No walkthroughs saved for this ROM yet."
      />

      <v-expansion-panels v-else v-model="savedOpenPanels" multiple>
        <v-expansion-panel
          v-for="wt in walkthroughs"
          :key="wt.id"
          :value="wt.id"
          elevation="0"
        >
          <v-expansion-panel-title class="bg-toplayer">
            <div class="d-flex align-center">
              <v-chip size="small" class="mr-2" color="primary">
                {{ wt.source }}
              </v-chip>
              <div class="d-flex flex-column">
                <div class="text-body-2 font-weight-medium">
                  {{ wt.title || wt.url }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  <span v-if="wt.author"> By {{ wt.author }} </span>
                  <span v-else>{{ wt.url }}</span>
                </div>
              </div>
            </div>
            <template #actions>
              <v-btn
                icon="mdi-open-in-new"
                variant="text"
                size="small"
                :href="wt.url"
                target="_blank"
                class="mr-1"
              />
              <v-btn
                icon="mdi-delete"
                variant="text"
                size="small"
                :loading="removingId === wt.id"
                @click.stop="removeSavedWalkthrough(wt.id)"
              />
            </template>
          </v-expansion-panel-title>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>
