<script setup lang="ts">
import CreateUserDialog from "@/components/Administration/Users/Dialog/CreateUser.vue";
import DeleteUserDialog from "@/components/Administration/Users/Dialog/DeleteUser.vue";
import EditUserDialog from "@/components/Administration/Users/Dialog/EditUser.vue";
import CreateExclusionDialog from "@/components/Management/Dialog/CreateExclusion.vue";
import CreatePlatformBindingDialog from "@/components/Management/Dialog/CreatePlatformBinding.vue";
import CreatePlatformVersionDialog from "@/components/Management/Dialog/CreatePlatformVersion.vue";
import DeletePlatformBindingDialog from "@/components/Management/Dialog/DeletePlatformBinding.vue";
import DeletePlatformVersionDialog from "@/components/Management/Dialog/DeletePlatformVersion.vue";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import CopyRomDownloadLinkDialog from "@/components/common/Game/Dialog/CopyDownloadLink.vue";
import DeleteRomDialog from "@/components/common/Game/Dialog/DeleteRom.vue";
import EditRomDialog from "@/components/common/Game/Dialog/EditRom.vue";
import MatchRomDialog from "@/components/common/Game/Dialog/MatchRom.vue";
import SearchRomDialog from "@/components/common/Game/Dialog/SearchRom.vue";
import UploadRomDialog from "@/components/common/Game/Dialog/UploadRom.vue";
import LoadingView from "@/components/common/LoadingView.vue";
import NewVersion from "@/components/common/NewVersion.vue";
import DeletePlatformDialog from "@/components/common/Platform/Dialog/DeletePlatform.vue";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import RommIso from "@/components/common/RommIso.vue";
import identityApi from "@/services/api/identity";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const navigationStore = storeNavigation();
const platformsStore = storePlatforms();
const { activePlatformsDrawer, activeSettingsDrawer } =
  storeToRefs(navigationStore);
const router = useRouter();
const auth = storeAuth();
const refreshView = ref(0);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});
emitter?.on("refreshView", async () => {
  refreshView.value = refreshView.value + 1;
});

// Functions
function goHome() {
  navigationStore.resetDrawers();
  router.push({ name: "dashboard" });
}

function goScan() {
  navigationStore.resetDrawers();
  router.push({ name: "scan" });
}

function togglePlatformsDrawer() {
  activeSettingsDrawer.value = false;
  navigationStore.switchActivePlatformsDrawer();
}

function toggleSettingsDrawer() {
  activePlatformsDrawer.value = false;
  navigationStore.switchActiveSettingsDrawer();
}

async function logout() {
  identityApi
    .logout()
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      router.push({ name: "login" });
    })
    .catch(() => {
      router.push({ name: "login" });
    })
    .finally(() => {
      auth.setUser(null);
    });
}

onMounted(async () => {
  navigationStore.resetDrawers();
  await userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });

  await platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>

<template>
  <v-progress-linear
    color="romm-accent-1"
    :active="scanning"
    :indeterminate="true"
    absolute
  />

  <!-- TODO: refactor and extract components -->
  <v-navigation-drawer
    v-if="!smAndDown"
    permanent
    rail
    :floating="activePlatformsDrawer || activeSettingsDrawer"
    rail-width="60"
  >
    <template #prepend>
      <v-row no-gutters class="my-2 justify-center">
        <router-link :to="{ name: 'dashboard' }">
          <v-hover v-slot="{ isHovering, props: hoverProps }">
            <romm-iso
              v-bind="hoverProps"
              :class="{ 'border-romm-accent-1': isHovering }"
              :size="40"
            />
          </v-hover>
        </router-link>
      </v-row>
      <v-row no-gutters class="my-4 justify-center">
        <v-btn
          icon="mdi-magnify"
          size="small"
          variant="flat"
          @click="emitter?.emit('showSearchRomDialog', null)"
        />
        <v-btn
          v-if="auth.scopes.includes('roms.write')"
          icon="mdi-upload"
          size="small"
          variant="flat"
          @click="emitter?.emit('showUploadRomDialog', null)"
        />
      </v-row>
    </template>
    <v-row no-gutters class="justify-center">
      <v-btn
        block
        rounded="0"
        variant="flat"
        :color="activePlatformsDrawer ? 'terciary' : ''"
        icon
        @click="togglePlatformsDrawer"
        ><v-icon :color="$route.name == 'platform' ? 'romm-accent-1' : ''"
          >mdi-controller</v-icon
        ></v-btn
      >
      <v-btn
        v-if="auth.scopes.includes('platforms.write')"
        block
        rounded="0"
        variant="flat"
        color="primary"
        icon
        @click="goScan"
        ><v-icon :color="$route.name == 'scan' ? 'romm-accent-1' : ''"
          >mdi-magnify-scan</v-icon
        ></v-btn
      >
    </v-row>
    <template #append>
      <v-row no-gutters class="justify-center">
        <v-hover v-slot="{ isHovering, props: hoverProps }">
          <v-avatar
            v-bind="hoverProps"
            :class="{ 'border-romm-accent-1': isHovering }"
            @click="toggleSettingsDrawer"
            size="35"
            class="my-2 pointer"
          >
            <v-img
              :src="
                auth.user?.avatar_path
                  ? `/assets/romm/assets/${auth.user?.avatar_path}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </v-hover>
      </v-row>
    </template>
  </v-navigation-drawer>

  <v-app-bar
    v-if="smAndDown"
    :elevation="0"
    class="bg-primary justify-center"
    mode="shift"
    height="45"
  >
    <template #prepend>
      <v-hover v-slot="{ isHovering, props: hoverProps }">
        <romm-iso
          @click="goHome"
          v-bind="hoverProps"
          class="pointer ml-1"
          :class="{ 'border-romm-accent-1': isHovering }"
          :size="35"
        />
      </v-hover>
    </template>

    <v-btn
      rounded="0"
      variant="flat"
      :color="activePlatformsDrawer ? 'terciary' : ''"
      icon
      @click="togglePlatformsDrawer"
      ><v-icon :color="$route.name == 'platform' ? 'romm-accent-1' : ''"
        >mdi-controller</v-icon
      ></v-btn
    >
    <v-btn
      v-if="auth.scopes.includes('platforms.write')"
      rounded="0"
      variant="flat"
      color="primary"
      icon
      @click="goScan"
      ><v-icon :color="$route.name == 'scan' ? 'romm-accent-1' : ''"
        >mdi-magnify-scan</v-icon
      ></v-btn
    >
    <template #append>
      <v-btn
        icon="mdi-magnify"
        size="small"
        variant="flat"
        @click="emitter?.emit('showSearchRomDialog', null)"
      />
      <v-btn
        v-if="auth.scopes.includes('roms.write')"
        icon="mdi-upload"
        size="small"
        variant="flat"
        class="mr-1"
        @click="emitter?.emit('showUploadRomDialog', null)"
      />
      <v-hover v-slot="{ isHovering, props: hoverProps }">
        <v-avatar
          @click="toggleSettingsDrawer"
          class="mr-1 pointer"
          size="35"
          v-bind="hoverProps"
          :class="{ 'border-romm-accent-1': isHovering }"
        >
          <v-img
            :src="
              auth.user?.avatar_path
                ? `/assets/romm/assets/${auth.user?.avatar_path}`
                : defaultAvatarPath
            "
          />
        </v-avatar>
      </v-hover>
    </template>
  </v-app-bar>

  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="400"
    v-model="activePlatformsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <platform-list-item
        v-for="platform in platformsStore.filledPlatforms"
        :key="platform.slug"
        :platform="platform"
        class="py-4"
      />
    </v-list>
  </v-navigation-drawer>

  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="300"
    v-model="activeSettingsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <v-list-img>
        <v-img
          :src="
            auth.user?.avatar_path
              ? `/assets/romm/assets/${auth.user?.avatar_path}`
              : defaultAvatarPath
          "
          :aspect-ratio="smAndDown ? 20 / 1 : 20 / 3"
          cover
        >
        </v-img>
      </v-list-img>
      <v-list-item class="mb-1 text-shadow text-white">
        <template #title>
          <span>{{ auth.user?.username }}</span>
        </template>
        <template #subtitle>
          <span>{{ auth.user?.role }}</span>
        </template>
      </v-list-item>
    </v-list>
    <v-list rounded="0" class="pa-0">
      <v-list-item :to="{ name: 'settings' }" append-icon="mdi-palette"
        >UI Settings</v-list-item
      >
      <v-list-item
        v-if="auth.scopes.includes('platforms.write')"
        append-icon="mdi-table-cog"
        :to="{ name: 'management' }"
        >Library Management
      </v-list-item>
      <v-list-item
        v-if="auth.scopes.includes('users.write')"
        :to="{ name: 'administration' }"
        append-icon="mdi-security"
        >Administration</v-list-item
      >
      <template v-if="smAndDown">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit"
          >Logout</v-list-item
        >
      </template>
    </v-list>
    <template v-if="!smAndDown" #append>
      <v-list rounded="0" class="pa-0">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit"
          >Logout</v-list-item
        >
      </v-list>
    </template>
  </v-navigation-drawer>

  <new-version />
  <router-view :key="refreshView" />

  <delete-platform-dialog />
  <search-rom-dialog />
  <match-rom-dialog />
  <copy-rom-download-link-dialog />
  <upload-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <delete-asset-dialog />
  <create-platform-binding-dialog />
  <delete-platform-binding-dialog />
  <create-platform-version-dialog />
  <delete-platform-version-dialog />
  <create-exclusion-dialog />
  <create-user-dialog />
  <edit-user-dialog />
  <delete-user-dialog />
  <loading-view />
</template>
<style scoped>
.v-progress-linear,
.v-bottom-navigation {
  z-index: 9999 !important;
}
</style>
