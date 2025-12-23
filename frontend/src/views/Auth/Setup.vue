<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import PlatformGroupList from "@/components/Setup/PlatformGroupList.vue";
import RDialog from "@/components/common/RDialog.vue";
import router from "@/plugins/router";
import { ROUTES } from "@/plugins/router";
import { refetchCSRFToken } from "@/services/api";
import setupApi from "@/services/api/setup";
import type { SetupLibraryInfo } from "@/services/api/setup";
import userApi from "@/services/api/user";
import storeHeartbeat from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { xs } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const usersStore = storeUsers();
const visiblePassword = ref(false);
const visibleRepeatPassword = ref(false);
const repeatPassword = ref("");

// Library setup state
const libraryInfo = ref<SetupLibraryInfo | null>(null);
const loadingLibraryInfo = ref(false);
const selectedPlatforms = ref<string[]>([]);
const creatingPlatforms = ref(false);
const openPanels = ref<number[]>([]);
const mobileTab = ref(0); // 0: Detected, 1: Available
const showConfirmDialog = ref(false);
const confirmDialogMessage = ref("");
const confirmDialogAction = ref<(() => void) | null>(null);

// Use a computed property to reactively update metadataOptions based on heartbeat
const metadataOptions = computed(() => [
  {
    name: "IGDB",
    value: "igdb",
    logo_path: "/assets/scrappers/igdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
  },
  {
    name: "MobyGames",
    value: "moby",
    logo_path: "/assets/scrappers/moby.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
  },
  {
    name: "ScreenScraper",
    value: "ss",
    logo_path: "/assets/scrappers/ss.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.SS_API_ENABLED,
  },
  {
    name: "RetroAchievements",
    value: "ra",
    logo_path: "/assets/scrappers/ra.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.RA_API_ENABLED,
  },
  {
    name: "Hasheous",
    value: "hasheous",
    logo_path: "/assets/scrappers/hasheous.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED,
  },
  {
    name: "Launchbox",
    value: "launchbox",
    logo_path: "/assets/scrappers/launchbox.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED,
  },
  {
    name: "Flashpoint Project",
    value: "flashpoint",
    logo_path: "/assets/scrappers/flashpoint.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.FLASHPOINT_API_ENABLED,
  },
  {
    name: "HowLongToBeat",
    value: "hltb",
    logo_path: "/assets/scrappers/hltb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.HLTB_API_ENABLED,
  },
  {
    name: "SteamgridDB",
    value: "sgdb",
    logo_path: "/assets/scrappers/sgdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED,
  },
]);

const defaultAdminUser = ref({
  username: "",
  password: "",
  email: "",
  role: "admin",
});

const step = ref(1); // 1: Library setup, 2: Create admin user , 3: Check metadata sources
const filledAdminUser = computed(
  () =>
    defaultAdminUser.value.username != "" &&
    defaultAdminUser.value.password != "" &&
    repeatPassword.value != "" &&
    defaultAdminUser.value.password === repeatPassword.value,
);
const isFirstStep = computed(() => step.value == 1);
const isLastStep = computed(() => step.value == 3);
const selectAll = ref(false);

// Helper function to group platforms by manufacturer
const groupPlatformsByManufacturer = (platforms: Platform[]) => {
  const groups: Record<string, Platform[]> = {};

  platforms.forEach((platform) => {
    const key = platform.family_name || "Other";
    if (!groups[key]) groups[key] = [];
    groups[key].push(platform);
  });

  // Sort platforms within groups and return sorted entries
  return Object.entries(groups)
    .map(
      ([groupName, platforms]) =>
        [
          groupName,
          platforms.sort((a, b) => {
            // Sort by generation within same family
            const aGen = a.generation ?? -1;
            const bGen = b.generation ?? -1;
            if (aGen > bGen) return 1;
            if (aGen < bGen) return -1;
            return a.name.localeCompare(b.name);
          }),
        ] as [string, Platform[]],
    )
    .sort(([a], [b]) => {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      return a.localeCompare(b);
    });
};

// Group existing platforms
const groupedExistingPlatforms = computed(() => {
  if (!libraryInfo.value) return [];

  // Only show existing platforms if a structure was actually detected
  if (!libraryInfo.value.detected_structure) return [];

  // Get supported platform slugs for quick lookup
  const supportedSlugs = new Set(
    libraryInfo.value.supported_platforms.map((p) => p.fs_slug),
  );

  // Get existing platform slugs
  const existingSlugs = libraryInfo.value.existing_platforms.map(
    (p) => p.fs_slug,
  );

  // Create a lookup map for rom counts
  const romCountMap = new Map(
    libraryInfo.value.existing_platforms.map((p) => [p.fs_slug, p.rom_count]),
  );

  // Get identified platforms (existing and in supported list)
  const identified = libraryInfo.value.supported_platforms
    .filter((p) => existingSlugs.includes(p.fs_slug))
    .map((p) => ({
      ...p,
      rom_count: romCountMap.get(p.fs_slug) || 0,
    }));

  // Get unidentified platforms (existing but not in supported list)
  // Create Platform objects for them with family_name="Other"
  const unidentified = libraryInfo.value.existing_platforms
    .filter((ep) => !supportedSlugs.has(ep.fs_slug))
    .map(
      (ep) =>
        ({
          fs_slug: ep.fs_slug,
          slug: ep.fs_slug,
          name: ep.fs_slug,
          family_name: "Other",
          generation: 999,
          rom_count: ep.rom_count,
        }) as Platform,
    );

  // Combine both and group them
  return groupPlatformsByManufacturer([...identified, ...unidentified]);
});

// Group available platforms (not existing)
const groupedAvailablePlatforms = computed(() => {
  if (!libraryInfo.value) return [];
  const existingSlugs = libraryInfo.value.existing_platforms.map(
    (p) => p.fs_slug,
  );
  const available = libraryInfo.value.supported_platforms
    .filter((p) => !existingSlugs.includes(p.fs_slug))
    .map((p) => ({
      ...p,
      rom_count: 0,
    }));
  return groupPlatformsByManufacturer(available);
});

// Check if there are existing platforms
const hasExistingPlatforms = computed(() => {
  // Only consider platforms as existing if a structure was detected
  if (!libraryInfo.value?.detected_structure) return false;
  return (libraryInfo.value?.existing_platforms.length ?? 0) > 0;
});

// Check if platform already exists
const isPlatformExisting = (fsSlug: string) => {
  return (
    libraryInfo.value?.existing_platforms.some((p) => p.fs_slug === fsSlug) ??
    false
  );
};

// Watch grouped existing and available platforms to open all panels
watch(
  [groupedExistingPlatforms, groupedAvailablePlatforms],
  ([existing, available]) => {
    const totalGroups = existing.length + available.length;
    if (totalGroups > 0) {
      openPanels.value = Array.from({ length: totalGroups }, (_, i) => i);
    }
  },
  { immediate: true },
);

// Watch selectAll to toggle all available platforms
watch(selectAll, (newValue) => {
  if (!libraryInfo.value) return;

  const existingSlugs = libraryInfo.value.existing_platforms.map(
    (p) => p.fs_slug,
  );

  if (newValue) {
    // Select all available platforms (exclude existing ones)
    const allAvailable = libraryInfo.value.supported_platforms
      .filter((p) => !existingSlugs.includes(p.fs_slug))
      .map((p) => p.fs_slug);
    selectedPlatforms.value = [...existingSlugs, ...allAvailable];
  } else {
    // Keep only existing platforms selected
    selectedPlatforms.value = [...existingSlugs];
  }
});

// Function to toggle all platforms in a group
function toggleGroupSelection(platforms: Platform[], checked: boolean) {
  const slugs = platforms.map((p) => p.fs_slug);
  if (checked) {
    // Add all platforms from this group
    const newSlugs = slugs.filter(
      (slug) => !selectedPlatforms.value.includes(slug),
    );
    selectedPlatforms.value = [...selectedPlatforms.value, ...newSlugs];
  } else {
    // Remove all platforms from this group
    selectedPlatforms.value = selectedPlatforms.value.filter(
      (slug) => !slugs.includes(slug),
    );
  }
}

// Check if all platforms in a group are selected
function isGroupFullySelected(platforms: Platform[]) {
  return platforms.every((p) => selectedPlatforms.value.includes(p.fs_slug));
}

// Compute the count of selected available platforms (excluding existing ones)
const selectedAvailableCount = computed(() => {
  const existingSlugs =
    libraryInfo.value?.existing_platforms.map((p) => p.fs_slug) || [];
  return selectedPlatforms.value.filter((slug) => !existingSlugs.includes(slug))
    .length;
});

// Compute the total game count for detected platforms
const totalDetectedGames = computed(() => {
  if (!libraryInfo.value?.existing_platforms) return 0;
  return libraryInfo.value.existing_platforms.reduce(
    (total, p) => total + p.rom_count,
    0,
  );
});

// Function to handle next button with confirmation
function handleNext(nextCallback: () => void) {
  if (step.value !== 1) {
    nextCallback();
    return;
  }

  const hasStructure = libraryInfo.value?.detected_structure;
  const platformsToCreate = selectedPlatforms.value.filter(
    (slug) => !isPlatformExisting(slug),
  );

  // Case 1: No structure detected and user is creating platforms
  if (!hasStructure && platformsToCreate.length > 0) {
    confirmDialogMessage.value = t("setup.confirm-no-structure", {
      count: platformsToCreate.length,
      plural: platformsToCreate.length > 1 ? "s" : "",
    });
    confirmDialogAction.value = nextCallback;
    showConfirmDialog.value = true;
    return;
  }

  // Case 2: No structure detected and user is not selecting anything
  if (!hasStructure && platformsToCreate.length === 0) {
    confirmDialogMessage.value = t("setup.confirm-no-platforms");
    confirmDialogAction.value = nextCallback;
    showConfirmDialog.value = true;
    return;
  }

  // Case 3: Structure is detected and user selected at least one platform to create
  if (hasStructure && platformsToCreate.length > 0 && libraryInfo.value) {
    const structurePattern =
      libraryInfo.value.detected_structure === "A"
        ? "roms/{platform}"
        : "{platform}/roms";
    confirmDialogMessage.value = t("setup.confirm-create-platforms", {
      structure: libraryInfo.value.detected_structure,
      pattern: structurePattern,
      count: platformsToCreate.length,
      plural: platformsToCreate.length > 1 ? "s" : "",
    });
    confirmDialogAction.value = nextCallback;
    showConfirmDialog.value = true;
    return;
  }

  // Otherwise, proceed normally
  nextCallback();
}

function handleConfirmDialog() {
  showConfirmDialog.value = false;
  if (confirmDialogAction.value) {
    confirmDialogAction.value();
    confirmDialogAction.value = null;
  }
}

async function loadLibraryInfo() {
  loadingLibraryInfo.value = true;
  try {
    const response = await setupApi.getLibraryInfo();
    libraryInfo.value = response.data;

    // Pre-check existing platforms
    selectedPlatforms.value = [
      ...(libraryInfo.value.existing_platforms.map((p) => p.fs_slug) || []),
    ];
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: `Failed to load library info: ${
        error.response?.data?.detail || error.message
      }`,
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    loadingLibraryInfo.value = false;
  }
}

async function finishWizard() {
  // First create platform folders if any selected
  const platformsToCreate = selectedPlatforms.value.filter(
    (slug) => !isPlatformExisting(slug),
  );

  if (platformsToCreate.length > 0) {
    creatingPlatforms.value = true;
    try {
      const response = await setupApi.createPlatforms(platformsToCreate);

      emitter?.emit("snackbarShow", {
        msg: response.data.message,
        icon: "mdi-check-circle",
        color: "success",
      });
    } catch (error: any) {
      emitter?.emit("snackbarShow", {
        msg: `Failed to create platform folders: ${
          error.response?.data?.detail || error.message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
      creatingPlatforms.value = false;
      return; // Stop if folder creation fails
    } finally {
      creatingPlatforms.value = false;
    }
  }

  // Then create admin user
  await userApi
    .createUser(defaultAdminUser.value)
    .then(async () => {
      await refetchCSRFToken();
      await heartbeat.fetchHeartbeat();
      router.push({ name: ROUTES.LOGIN });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to create user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
}

onMounted(() => {
  loadLibraryInfo();
});
</script>

<template>
  <v-card
    class="translucent px-3 d-flex flex-column"
    width="1100"
    height="85dvh"
  >
    <v-card-title>
      <v-img src="/assets/isotipo.svg" class="mx-auto mt-6" width="70" />
    </v-card-title>
    <v-stepper
      v-model="step"
      :mobile="xs"
      class="bg-transparent d-flex flex-column flex-grow-1"
      flat
    >
      <template #default="{ prev, next }">
        <div class="flex-grow-0">
          <v-stepper-header style="box-shadow: unset">
            <v-stepper-item :value="1">
              <template #title>
                <span class="text-white text-shadow">{{
                  t("setup.library-structure-step")
                }}</span>
              </template>
            </v-stepper-item>

            <v-divider />

            <v-stepper-item :value="2">
              <template #title>
                <span class="text-white text-shadow">{{
                  t("setup.admin-user-step")
                }}</span>
              </template>
            </v-stepper-item>

            <v-divider />

            <v-stepper-item :value="3">
              <template #title>
                <span class="text-white text-shadow">{{
                  t("setup.check-metadata-step")
                }}</span>
              </template>
            </v-stepper-item>
          </v-stepper-header>
        </div>

        <!-- Mobile title section -->
        <div v-if="xs" class="flex-grow-0 text-center">
          <span class="text-white text-shadow text-subtitle-1">
            <span v-if="step === 1">{{
              t("setup.library-structure-step")
            }}</span>
            <span v-else-if="step === 2">{{ t("setup.admin-user-step") }}</span>
            <span v-else-if="step === 3">{{
              t("setup.check-metadata-step")
            }}</span>
          </span>
        </div>

        <v-stepper-window
          class="flex-grow-1 mb-4 scroll"
          :class="{ 'align-content-center': step != 1 || loadingLibraryInfo }"
        >
          <v-stepper-window-item :key="1" :value="1" class="h-100">
            <v-row no-gutters class="h-100">
              <v-col class="h-100">
                <!-- Fixed header section -->
                <!-- Loading state -->
                <v-row
                  v-if="loadingLibraryInfo"
                  class="justify-center align-center"
                  no-gutters
                >
                  <v-col class="text-center py-8">
                    <v-progress-circular
                      indeterminate
                      color="primary"
                      size="64"
                    />
                  </v-col>
                </v-row>

                <template v-else>
                  <!-- Structure info -->
                  <v-row no-gutters class="mb-3">
                    <v-col class="text-center">
                      <p class="text-white text-shadow">
                        <strong>{{ t("setup.folder-structure") }}:</strong>
                        {{
                          libraryInfo?.detected_structure === "A"
                            ? t("setup.structure-a-detected")
                            : libraryInfo?.detected_structure === "B"
                              ? t("setup.structure-b-detected")
                              : t("setup.no-structure-detected")
                        }}
                      </p>
                      <p class="text-caption text-grey">
                        {{
                          libraryInfo?.detected_structure === "A" ||
                          !libraryInfo?.detected_structure
                            ? "roms/{platform}"
                            : "{platform}/roms"
                        }}
                      </p>
                    </v-col>
                  </v-row>

                  <!-- Scrollable platform selection section -->
                  <v-row no-gutters>
                    <!-- Desktop: Two columns side by side -->
                    <template v-if="!xs">
                      <!-- Existing platforms column -->
                      <v-col
                        v-if="hasExistingPlatforms"
                        cols="12"
                        md="6"
                        class="pr-2"
                      >
                        <div class="text-white text-center text-shadow mb-2">
                          <strong>{{ t("setup.detected-platforms") }}</strong>
                        </div>
                        <div class="mb-2 ml-4">
                          <v-chip label>
                            {{ libraryInfo?.existing_platforms.length }}
                            {{ t("setup.platforms") }}
                          </v-chip>
                          <v-chip class="ml-2" variant="tonal" label>
                            {{ totalDetectedGames }}
                            {{
                              totalDetectedGames !== 1
                                ? t("setup.games")
                                : t("setup.game")
                            }}
                          </v-chip>
                        </div>
                        <PlatformGroupList
                          :grouped-platforms="groupedExistingPlatforms"
                        />
                      </v-col>

                      <!-- Available platforms to create column -->
                      <v-col
                        cols="12"
                        :md="hasExistingPlatforms ? 6 : 12"
                        class="pl-2"
                      >
                        <div class="text-white text-center text-shadow mb-2">
                          <strong>{{
                            hasExistingPlatforms
                              ? t("setup.available-platforms")
                              : t("setup.select-platforms")
                          }}</strong>
                        </div>
                        <div class="mb-2 ml-4">
                          <v-chip
                            variant="tonal"
                            color="primary"
                            @click="selectAll = !selectAll"
                            label
                          >
                            {{
                              selectAll
                                ? t("setup.deselect-all")
                                : t("setup.select-all")
                            }}
                          </v-chip>
                          <v-chip class="ml-2" label
                            >{{ selectedAvailableCount }}
                            {{ t("setup.selected") }}</v-chip
                          >
                        </div>
                        <PlatformGroupList
                          :grouped-platforms="groupedAvailablePlatforms"
                          v-model:selected-platforms="selectedPlatforms"
                          :show-checkboxes="true"
                          key-prefix="available"
                          :base-index="groupedExistingPlatforms.length"
                          :on-toggle-group="toggleGroupSelection"
                          :is-group-fully-selected="isGroupFullySelected"
                        />
                      </v-col>
                    </template>

                    <!-- Mobile: Tabs for each section -->
                    <v-col v-else cols="12">
                      <v-tabs v-model="mobileTab" centered grow class="mb-3">
                        <v-tab
                          v-if="hasExistingPlatforms"
                          :value="0"
                          class="text-white text-shadow"
                        >
                          {{ t("setup.detected-platforms") }}
                        </v-tab>
                        <v-tab
                          :value="hasExistingPlatforms ? 1 : 0"
                          class="text-white text-shadow"
                        >
                          {{ t("setup.available-platforms") }}
                        </v-tab>
                      </v-tabs>

                      <v-window v-model="mobileTab">
                        <!-- Detected platforms tab -->
                        <v-window-item v-if="hasExistingPlatforms" :value="0">
                          <div class="mb-2 ml-4">
                            <v-chip label>
                              {{ libraryInfo?.existing_platforms.length }}
                              {{ t("setup.platforms") }}
                            </v-chip>
                            <v-chip class="ml-2" variant="tonal" label>
                              {{ totalDetectedGames }}
                              {{
                                totalDetectedGames !== 1
                                  ? t("setup.games")
                                  : t("setup.game")
                              }}
                            </v-chip>
                          </div>
                          <PlatformGroupList
                            :grouped-platforms="groupedExistingPlatforms"
                            key-prefix="existing-mobile"
                          />
                        </v-window-item>

                        <!-- Available platforms tab -->
                        <v-window-item :value="hasExistingPlatforms ? 1 : 0">
                          <div class="mb-2 ml-4">
                            <v-chip
                              variant="tonal"
                              color="primary"
                              @click="selectAll = !selectAll"
                              label
                            >
                              {{
                                selectAll
                                  ? t("setup.deselect-all")
                                  : t("setup.select-all")
                              }}
                            </v-chip>
                            <v-chip class="ml-2" label
                              >{{ selectedAvailableCount }}
                              {{ t("setup.selected") }}</v-chip
                            >
                          </div>
                          <PlatformGroupList
                            :grouped-platforms="groupedAvailablePlatforms"
                            v-model:selected-platforms="selectedPlatforms"
                            :show-checkboxes="true"
                            key-prefix="available-mobile"
                            :base-index="groupedExistingPlatforms.length"
                            :on-toggle-group="toggleGroupSelection"
                            :is-group-fully-selected="isGroupFullySelected"
                          />
                        </v-window-item>
                      </v-window>
                    </v-col>
                  </v-row>
                </template>
              </v-col>
            </v-row>
          </v-stepper-window-item>

          <v-stepper-window-item :key="2" :value="2" class="h-100">
            <v-row no-gutters class="h-100">
              <v-col class="d-flex flex-column">
                <v-row
                  class="justify-center align-center flex-grow-1"
                  no-gutters
                >
                  <v-col cols="12" md="8">
                    <v-form @submit.prevent>
                      <v-text-field
                        v-model="defaultAdminUser.username"
                        :label="`${t('settings.username')} *`"
                        type="text"
                        :rules="usersStore.usernameRules"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-account"
                        variant="underlined"
                      />
                      <v-text-field
                        v-model="defaultAdminUser.email"
                        :label="`${t('settings.email')} *`"
                        type="text"
                        :rules="usersStore.emailRules"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-account"
                        variant="underlined"
                      />
                      <v-text-field
                        v-model="defaultAdminUser.password"
                        :label="`${t('settings.password')} *`"
                        :type="visiblePassword ? 'text' : 'password'"
                        :rules="usersStore.passwordRules"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-lock"
                        :append-inner-icon="
                          visiblePassword ? 'mdi-eye-off' : 'mdi-eye'
                        "
                        variant="underlined"
                        @click:append-inner="visiblePassword = !visiblePassword"
                      />
                      <v-text-field
                        v-model="repeatPassword"
                        :label="`${t('settings.repeat-password')} *`"
                        :type="visibleRepeatPassword ? 'text' : 'password'"
                        :rules="[
                          (v: string) =>
                            !!v || t('settings.repeat-password-required'),
                          (v: string) =>
                            v === defaultAdminUser.password ||
                            t('settings.passwords-must-match'),
                        ]"
                        required
                        autocomplete="on"
                        prepend-inner-icon="mdi-lock"
                        :append-inner-icon="
                          visibleRepeatPassword ? 'mdi-eye-off' : 'mdi-eye'
                        "
                        variant="underlined"
                        @click:append-inner="
                          visibleRepeatPassword = !visibleRepeatPassword
                        "
                        @keydown.enter="filledAdminUser && next()"
                      />
                    </v-form>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
          </v-stepper-window-item>

          <v-stepper-window-item :key="3" :value="3" class="h-100">
            <v-row no-gutters class="h-100">
              <v-col class="d-flex flex-column">
                <v-row
                  class="justify-center align-center flex-grow-1"
                  no-gutters
                >
                  <v-col cols="12" sm="8">
                    <v-list-item
                      v-for="source in metadataOptions"
                      :key="source.value"
                      class="text-white text-shadow"
                      :title="source.name"
                      :subtitle="
                        source.disabled ? t('setup.metadata-missing') : ''
                      "
                    >
                      <template #prepend>
                        <v-avatar variant="text" size="30" rounded="1">
                          <v-img :src="source.logo_path" />
                        </v-avatar>
                      </template>
                      <template #append>
                        <span v-if="source.disabled" class="ml-2">❌</span>
                        <span v-else class="ml-2">✅</span>
                      </template>
                    </v-list-item>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
          </v-stepper-window-item>
        </v-stepper-window>

        <div class="flex-grow-0">
          <v-stepper-actions :disabled="step == 2 && !filledAdminUser">
            <template #prev>
              <v-btn
                class="text-white text-shadow"
                :ripple="false"
                :disabled="isFirstStep"
                @click="prev"
              >
                {{ isFirstStep ? "" : t("setup.previous") }}
              </v-btn>
            </template>
            <template #next>
              <v-btn
                class="text-white text-shadow"
                :loading="isLastStep && creatingPlatforms"
                @click="!isLastStep ? handleNext(next) : finishWizard()"
                @keydown.enter="!isLastStep ? handleNext(next) : finishWizard()"
              >
                {{ !isLastStep ? t("setup.next") : t("setup.finish") }}
              </v-btn>
            </template>
          </v-stepper-actions>
        </div>
      </template>
    </v-stepper>

    <!-- Confirmation Dialog -->
    <RDialog
      v-model="showConfirmDialog"
      icon="mdi-alert"
      width="500"
      @close="showConfirmDialog = false"
    >
      <template #content>
        <div class="text-body-1 pa-4">
          {{ confirmDialogMessage }}
        </div>
      </template>
      <template #footer>
        <v-row class="justify-center my-2" no-gutters>
          <v-btn-group divided density="compact">
            <v-btn class="bg-toplayer" @click="showConfirmDialog = false">
              {{ t("setup.cancel") }}
            </v-btn>
            <v-btn
              class="bg-toplayer text-primary"
              @click="handleConfirmDialog"
            >
              {{ t("setup.continue") }}
            </v-btn>
          </v-btn-group>
        </v-row>
      </template>
    </RDialog>
  </v-card>
</template>
<style lang="css" scoped>
.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
