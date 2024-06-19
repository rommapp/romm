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
const { mdAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
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
const platformsDrawer = ref(false);
const settingsDrawer = ref(false);
const actionsDrawer = ref(false);

// Functions
function goHome() {
  platformsDrawer.value = false;
  settingsDrawer.value = false;
  router.push({ name: "dashboard" });
}
function goScan() {
  platformsDrawer.value = false;
  settingsDrawer.value = false;
  router.push({ name: "scan" });
}
function togglePlatformsDrawer() {
  platformsDrawer.value = !platformsDrawer.value;
  settingsDrawer.value = false;
  actionsDrawer.value = false;
}
function toggleSettingsDrawer() {
  platformsDrawer.value = false;
  settingsDrawer.value = !settingsDrawer.value;
  actionsDrawer.value = false;
}
function toggleActionsDrawer() {
  platformsDrawer.value = false;
  settingsDrawer.value = false;
  actionsDrawer.value = !actionsDrawer.value;
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

onMounted(() => {
  userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });

  platformApi
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
    :floating="platformsDrawer || settingsDrawer"
    rail
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
          v-if="auth.scopes.includes('roms.write')"
          icon="mdi-upload"
          variant="flat"
          @click="emitter?.emit('showUploadRomDialog', null)"
        />
        <v-btn
          icon="mdi-magnify"
          variant="flat"
          @click="emitter?.emit('showSearchRomDialog', null)"
        />
      </v-row>
    </template>
    <v-row no-gutters class="justify-center">
      <v-btn
        block
        rounded="0"
        variant="flat"
        :color="platformsDrawer ? 'terciary' : ''"
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
        <v-btn
          block
          rounded="0"
          variant="flat"
          :color="settingsDrawer ? 'terciary' : ''"
          icon
          @click="toggleSettingsDrawer"
          ><v-icon
            :color="
              $route.name == 'settings' ||
              $route.name == 'management' ||
              $route.name == 'administration'
                ? 'romm-accent-1'
                : ''
            "
            >mdi-cog</v-icon
          ></v-btn
        >
        <v-avatar size="35" class="my-2">
          <v-img
            :src="
              auth.user?.avatar_path
                ? `/assets/romm/assets/${auth.user?.avatar_path}`
                : defaultAvatarPath
            "
          />
        </v-avatar>
      </v-row>
    </template>
  </v-navigation-drawer>

  <v-navigation-drawer
    :location="mdAndDown ? 'bottom' : 'left'"
    mobile
    width="340"
    v-model="platformsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <platform-list-item
        v-for="platform in platformsStore.filledPlatforms"
        :key="platform.slug"
        :platform="platform"
        class="py-4"
      />
      <!-- This one list-item is needed to fix the marging issue with bottom navigation -->
      <v-list-item v-if="mdAndDown" />
    </v-list>
  </v-navigation-drawer>

  <v-navigation-drawer
    :location="mdAndDown ? 'bottom' : 'left'"
    mobile
    width="340"
    v-model="settingsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <v-img
        :src="
          auth.user?.avatar_path
            ? `/assets/romm/assets/${auth.user?.avatar_path}`
            : defaultAvatarPath
        "
        :aspect-ratio="20 / 3"
        cover
      >
        <v-list-item class="text-shadow">
          <template #title>
            <span>{{ auth.user?.username }}</span>
          </template>
          <template #subtitle>
            <span>{{ auth.user?.role }}</span>
          </template>
        </v-list-item>
      </v-img>
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
        <template v-if="mdAndDown">
          <v-divider />
          <v-list-item @click="logout" append-icon="mdi-location-exit"
            >Logout</v-list-item
          >
          <!-- This one list-item is needed to fix the marging issue with bottom navigation -->
          <v-list-item />
        </template>
      </v-list>
    </v-list>
    <template v-if="!mdAndDown" #append>
      <v-list rounded="0" class="pa-0">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit"
          >Logout</v-list-item
        >
      </v-list>
    </template>
  </v-navigation-drawer>

  <v-navigation-drawer
    location="bottom"
    mobile
    width="340"
    v-model="actionsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <v-list-item
        @click="emitter?.emit('showSearchRomDialog', null)"
        append-icon="mdi-magnify"
      >
        Search
      </v-list-item>
      <v-list-item
        @click="emitter?.emit('showUploadRomDialog', null)"
        append-icon="mdi-upload"
      >
        Upload
      </v-list-item>
      <!-- This one list-item is needed to fix the marging issue with bottom navigation -->
      <v-list-item v-if="mdAndDown" />
    </v-list>
  </v-navigation-drawer>

  <new-version />
  <router-view :key="refreshView" />

  <v-bottom-navigation
    v-if="mdAndDown"
    :elevation="0"
    class="bg-primary"
    mode="shift"
    height="45"
  >
    <v-btn @click="goHome">
      <v-icon>mdi-home</v-icon>
      <span>Home</span>
    </v-btn>
    <v-btn @click="togglePlatformsDrawer">
      <v-icon>mdi-controller</v-icon>
      <span>Platforms</span>
    </v-btn>
    <v-btn v-if="auth.scopes.includes('platforms.write')" @click="goScan">
      <v-icon>mdi-magnify-scan</v-icon>
      <span>Scan</span>
    </v-btn>
    <v-btn @click="toggleSettingsDrawer">
      <v-icon>mdi-cog</v-icon>
      <span>Settings</span>
    </v-btn>
    <v-btn @click="toggleActionsDrawer">
      <v-icon>mdi-dots-horizontal</v-icon>
      <span>Actions</span>
    </v-btn>
  </v-bottom-navigation>

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
