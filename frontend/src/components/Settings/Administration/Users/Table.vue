<script setup lang="ts">
import CreateUserDialog from "@/components/Settings/Administration/Users/Dialog/CreateUser.vue";
import InviteLinkDialog from "@/components/Settings/Administration/Users/Dialog/InviteLink.vue";
import DeleteUserDialog from "@/components/Settings/Administration/Users/Dialog/DeleteUser.vue";
import RSection from "@/components/common/RSection.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, formatTimestamp, getRoleIcon } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const userSearch = ref("");
const emitter = inject<Emitter<Events>>("emitter");
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const auth = storeAuth();
const HEADERS = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "avatar_path",
    width: "40px",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Email",
    align: "start",
    sortable: true,
    key: "email",
  },
  {
    title: "Role",
    align: "start",
    sortable: true,
    key: "role",
  },
  {
    title: "Last active",
    align: "start",
    sortable: true,
    key: "last_active",
  },
  {
    title: "Enabled",
    align: "start",
    sortable: true,
    key: "enabled",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

function disableUser(user: User) {
  userApi.updateUser(user).catch(({ response, message }) => {
    emitter?.emit("snackbarShow", {
      msg: `Unable to disable/enable user: ${
        response?.data?.detail || response?.statusText || message
      }`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 5000,
    });
  });
}

onMounted(() => {
  userApi
    .fetchUsers()
    .then(({ data }) => {
      usersStore.set(data);
    })
    .catch((error) => {
      console.log(error);
    });
});
</script>

<template>
  <r-section icon="mdi-account" title="Users" class="ma-2">
    <template #content>
      <v-text-field
        v-model="userSearch"
        prepend-inner-icon="mdi-magnify"
        label="Search"
        single-line
        hide-details
        clearable
        rounded="0"
        density="comfortable"
        class="bg-surface"
      />
      <v-data-table-virtual
        :style="{ 'max-height': '40dvh' }"
        :search="userSearch"
        :headers="HEADERS"
        :items="allUsers"
        :sort-by="[{ key: 'username', order: 'asc' }]"
        fixed-header
        fixed-footer
        density="comfortable"
        class="rounded bg-background"
        hide-default-footer
      >
        <template #header.actions>
          <v-btn-group divided density="compact">
            <v-btn
              prepend-icon="mdi-plus"
              variant="outlined"
              class="text-primary"
              @click="emitter?.emit('showCreateUserDialog', null)"
            >
              {{ t("common.add") }}
            </v-btn>
            <v-btn
              prepend-icon="mdi-share"
              variant="outlined"
              class="text-primary"
              @click="emitter?.emit('showCreateInviteLinkDialog')"
            >
              {{ t("settings.invite-link") }}
            </v-btn>
          </v-btn-group>
        </template>
        <template #item.avatar_path="{ item }">
          <v-avatar>
            <v-img
              :src="
                item.avatar_path
                  ? `/assets/romm/assets/${item.avatar_path}?ts=${item.updated_at}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </template>
        <template #item.username="{ item }">
          <v-list-item class="pa-0" min-width="120px">
            {{ item.username }}
          </v-list-item>
        </template>
        <template #item.role="{ item }">
          <v-list-item class="pa-0" min-width="100px">
            <v-icon class="mr-2">{{ getRoleIcon(item.role) }}</v-icon>
            {{ item.role }}
          </v-list-item>
        </template>
        <template #item.last_active="{ item }">
          {{ formatTimestamp(item.last_active) }}
        </template>
        <template #item.enabled="{ item }">
          <v-switch
            inset
            v-model="item.enabled"
            color="primary"
            :disabled="item.id == auth.user?.id"
            hide-details
            @change="disableUser(item)"
          />
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact">
            <v-btn
              size="small"
              @click="emitter?.emit('showEditUserDialog', item)"
            >
              <v-icon>mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              class="text-romm-red"
              size="small"
              @click="emitter?.emit('showDeleteUserDialog', item)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>
      </v-data-table-virtual>
    </template>
  </r-section>

  <create-user-dialog />
  <invite-link-dialog />
  <delete-user-dialog />
</template>
