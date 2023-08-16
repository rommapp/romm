<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { VDataTable } from "vuetify/labs/VDataTable";
import version from "../../../package";

// Props
const tab = ref("general");

// User CRUD
const usersHeaders = [
  {
    title: "Username",
    align: "start",
    sortable: true,
    key: "username",
  },
  {
    title: "Rol",
    align: "start",
    sortable: true,
    key: "rol",
  },
  { title: "Actions", align: "end", key: "actions", sortable: false },
];
const users = ref([
  {
    username: "User 1",
    rol: "Admin",
  },
  {
    username: "User 2",
    rol: "user",
  },
  {
    username: "User 3",
    rol: "Admin",
  },
  {
    username: "User 4",
    rol: "user"
  },
  {
    username: "User 5",
    rol: "user",
  },
  {
    username: "User 6",
    rol: "user",
  },
  {
    username: "User 7",
    rol: "Admin",
  },
  {
    username: "User 8",
    rol: "user",
  },
  {
    username: "User 9",
    rol: "Admin",
  },
  {
    username: "User 10",
    rol: "user",
  },
  {
    username: "User 13123",
    rol: "Admin",
  },
  {
    username: "User 2",
    rol: "user",
  },
  {
    username: "User 3",
    rol: "Admin",
  },
  {
    username: "User 4",
    rol: "user",
  },
  {
    username: "User 5",
    rol: "user",
  },
  {
    username: "User 6",
    rol: "user",
  },
  {
    username: "User 7",
    rol: "Admin",
  },
  {
    username: "User 8",
    rol: "user",
  },
  {
    username: "User 9",
    rol: "Admin",
  }
]);
const usersPerPage = ref(5);
const dialogCreate = ref(false);
const dialogEdit = ref(false);
const dialogDelete = ref(false);
const createdUser = ref({
  username: "",
  password: "",
  rol: "",
});
const editedUser = ref({
  id: "",
  username: "",
  password: "",
  rol: "",
});
const deletedUser = ref({
  id: "",
  username: "",
});
function createUser() {
  // TODO: call create user endpoint
  dialogCreate.value = false;
}
function editUser(user) {
  // TODO: call edit user endpoint
  editedUser.value = user;
  dialogEdit.value = true;
}
function deleteUser(user) {
  // TODO: call delete user endpoint
  deletedUser.value = user;
  dialogDelete.value = true;
}
// User CRUD

const theme = useTheme();
const darkMode =
  localStorage.getItem("theme") == "rommDark" ? ref(true) : ref(false);
const ROMM_VERSION = version.version;

// Functions
function toggleTheme() {
  theme.global.name.value = darkMode.value ? "rommDark" : "rommLight";
  darkMode.value
    ? localStorage.setItem("theme", "rommDark")
    : localStorage.setItem("theme", "rommLight");
}
</script>
<template>
  <!-- Settings tabs -->
  <v-app-bar elevation="0" density="compact">
    <v-tabs v-model="tab" slider-color="rommAccent1" class="bg-primary">
      <v-tab value="general" rounded="0"> General </v-tab>
      <v-tab value="ui" rounded="0">User Interface</v-tab>
    </v-tabs>
  </v-app-bar>

  <!-- General tab -->
  <v-window v-model="tab">
    <v-window-item value="general">
      <v-row class="pa-1">
        <v-col>
          <v-card rounded="0">
            <v-card-text class="pa-0">
              <v-data-table
                v-model:items-per-page="usersPerPage"
                :headers="usersHeaders"
                :items="users"
                :sort-by="[{ key: 'username', order: 'asc' }]"
              >
                <template v-slot:top>
                  <v-toolbar class="bg-terciary">
                    <v-toolbar-title
                      ><v-icon class="mr-3">mdi-account-group</v-icon
                      >Users</v-toolbar-title
                    >

                    <v-dialog
                      v-model="dialogCreate"
                      max-width="500px"
                      :scrim="false"
                    >
                      <template v-slot:activator="{ props }">
                        <v-btn
                          v-bind="props"
                          prepend-icon="mdi-plus"
                          variant="outlined"
                        >
                          Create user
                        </v-btn>
                      </template>
                      <v-card>
                        <v-toolbar density="compact" class="bg-terciary">
                          <v-row class="align-center" no-gutters>
                            <v-col cols="10">
                              <v-icon icon="mdi-account" class="ml-5 mr-2" />
                            </v-col>
                            <v-col>
                              <v-btn
                                @click="dialogCreate = false"
                                class="bg-terciary"
                                rounded="0"
                                variant="text"
                                icon="mdi-close"
                                block
                              />
                            </v-col>
                          </v-row>
                        </v-toolbar>
                        <v-divider class="border-opacity-25" :thickness="1" />

                        <v-card-text>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="createdUser.username"
                                label="username"
                                required
                                hide-details
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="createdUser.password"
                                label="Password"
                                required
                                hide-details
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-select
                                v-model="createdUser.rol"
                                rounded="0"
                                variant="outlined"
                                :items="['admin', 'user']"
                                label="Rol"
                                required
                                hide-details
                              ></v-select>
                            </v-col>
                          </v-row>
                          <v-row class="justify-center pa-2" no-gutters>
                            <v-btn
                              @click="dialogCreate = false"
                              class="bg-terciary"
                              >Cancel</v-btn
                            >
                            <v-btn
                              class="text-rommGreen bg-terciary ml-5"
                              @click="createUser()"
                              >Create</v-btn
                            >
                          </v-row>
                        </v-card-text>
                      </v-card>
                    </v-dialog>

                    <v-dialog
                      v-model="dialogEdit"
                      max-width="500px"
                      :scrim="false"
                    >
                      <v-card>
                        <v-toolbar density="compact" class="bg-terciary">
                          <v-row class="align-center" no-gutters>
                            <v-col cols="10">
                              <v-icon icon="mdi-pencil-box" class="ml-5 mr-2" />
                            </v-col>
                            <v-col>
                              <v-btn
                                @click="dialogEdit = false"
                                class="bg-terciary"
                                rounded="0"
                                variant="text"
                                icon="mdi-close"
                                block
                              />
                            </v-col>
                          </v-row>
                        </v-toolbar>
                        <v-divider class="border-opacity-25" :thickness="1" />

                        <v-card-text>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="editedUser.username"
                                label="username"
                                required
                                hide-details
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-text-field
                                rounded="0"
                                variant="outlined"
                                v-model="editedUser.password"
                                label="Password"
                                required
                                hide-details
                              ></v-text-field>
                            </v-col>
                          </v-row>
                          <v-row class="pa-2" no-gutters>
                            <v-col>
                              <v-select
                                v-model="editedUser.rol"
                                rounded="0"
                                variant="outlined"
                                :items="['admin', 'user']"
                                label="Rol"
                                required
                                hide-details
                              ></v-select>
                            </v-col>
                          </v-row>
                          <v-row class="justify-center pa-2" no-gutters>
                            <v-btn
                              @click="dialogEdit = false"
                              class="bg-terciary"
                              >Cancel</v-btn
                            >
                            <v-btn
                              class="text-rommGreen bg-terciary ml-5"
                              @click=""
                              >Apply</v-btn
                            >
                          </v-row>
                        </v-card-text>
                      </v-card>
                    </v-dialog>

                    <v-dialog
                      v-model="dialogDelete"
                      max-width="500px"
                      :scrim="true"
                    >
                      <v-card>
                        <v-toolbar density="compact" class="bg-terciary">
                          <v-row class="align-center" no-gutters>
                            <v-col cols="10">
                              <v-icon icon="mdi-delete" class="ml-5 mr-2" />
                            </v-col>
                            <v-col>
                              <v-btn
                                @click="dialogDelete = false"
                                class="bg-terciary"
                                rounded="0"
                                variant="text"
                                icon="mdi-close"
                                block
                              />
                            </v-col>
                          </v-row>
                        </v-toolbar>
                        <v-divider class="border-opacity-25" :thickness="1" />

                        <v-card-text>
                          <v-row class="justify-center pa-2" no-gutters>
                            <span class="mr-1">Deleting</span
                            ><span class="text-rommAccent1">{{
                              deletedUser.username
                            }}</span
                            >.<span class="ml-1">Do you confirm?</span>
                          </v-row>
                          <v-row class="justify-center pa-2" no-gutters>
                            <v-btn
                              @click="dialogDelete = false"
                              class="bg-terciary"
                              >Cancel</v-btn
                            >
                            <v-btn
                              class="bg-terciary text-rommRed ml-5"
                              @click=""
                              >Confirm</v-btn
                            >
                          </v-row>
                        </v-card-text>
                      </v-card>
                    </v-dialog>
                  </v-toolbar>
                </template>
                <template v-slot:item.actions="{ item }">
                  <v-icon class="me-2" @click="editUser(item.raw)">
                    mdi-pencil
                  </v-icon>
                  <v-icon class="text-red" @click="deleteUser(item.raw)"
                    >mdi-delete</v-icon
                  >
                </template>
              </v-data-table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-window-item>

    <!-- User Interface tab -->
    <v-window-item value="ui">
      <v-row class="pa-4" no-gutters>
        <v-switch
          @change="toggleTheme()"
          v-model="darkMode"
          prepend-icon="mdi-theme-light-dark"
          hide-details
          inset
        />
      </v-row>
    </v-window-item>
  </v-window>

  <v-bottom-navigation :elevation="0" height="36" class="text-caption">
    <v-row class="align-center justify-center" no-gutters>
      <span class="text-rommAccent1">RomM</span>
      <span class="ml-1">{{ ROMM_VERSION }}</span>
    </v-row>
  </v-bottom-navigation>
</template>
