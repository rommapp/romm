<script setup>
import { ref } from "vue";
import { useTheme } from "vuetify";
import { VDataTable } from "vuetify/labs/VDataTable";
import version from "../../../package";

// Props
const tab = ref("general");
const dialog = ref(false);
const dialogDelete = ref(false);
const editedIndex = ref(-1);
const editedItem = ref({
  name: "",
  rol: "",
});
const defaultItem = ref({
  name: "",
  rol: "",
});
const headers = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  {
    title: "Rol",
    align: "start",
    sortable: true,
    key: "rol",
  },
  { title: 'Actions', align: 'end', key: 'actions', sortable: false },
];
const users = ref([
  {
    name: "User 1",
    rol: "Admin",
  },
  {
    name: "User 2",
    rol: "Admin",
  },
  {
    name: "User 3",
    rol: "Admin",
  },
  {
    name: "User 4",
    rol: "Admin",
  },
  {
    name: "User 5",
    rol: "Admin",
  },
  {
    name: "User 6",
    rol: "Admin",
  },
  {
    name: "User 7",
    rol: "Admin",
  },
  {
    name: "User 8",
    rol: "Admin",
  },
  {
    name: "User 9",
    rol: "Admin",
  },
  {
    name: "User 10",
    rol: "Admin",
  }
]);
const itemsPerPage = ref(5);
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

  <v-window v-model="tab">
    <v-window-item value="general">
      <v-row class="pa-1">
        <v-col>
          <v-card rounded="0">
            <v-card-text class="pa-0">
              <v-data-table
                v-model:items-per-page="itemsPerPage"
                :headers="headers"
                :items="users"
                :sort-by="[{ key: 'name', order: 'asc' }]"
                class="elevation-1"
              >
                <template v-slot:top>
                  <v-toolbar flat class="bg-terciary">
                    <v-toolbar-title
                      ><v-icon class="mr-3">mdi-account-group</v-icon
                      >Users</v-toolbar-title
                    >
                    <v-divider class="mx-4" inset vertical></v-divider>
                    <v-spacer></v-spacer>
                    <v-dialog v-model="dialog" max-width="500px">
                      <template v-slot:activator="{ props }">
                        <v-btn color="primary" dark class="mb-2" v-bind="props">
                          New Item
                        </v-btn>
                      </template>
                      <v-card>
                        <v-card-title>
                          <span class="text-h5">{{ formTitle }}</span>
                        </v-card-title>

                        <v-card-text>
                          <v-container>
                            <v-row>
                              <v-col cols="12" sm="6" md="4">
                                <v-text-field
                                  v-model="editedItem.name"
                                  label="Name"
                                ></v-text-field>
                              </v-col>
                              <v-col cols="12" sm="6" md="4">
                                <v-text-field
                                  v-model="editedItem.rol"
                                  label="Rol"
                                ></v-text-field>
                              </v-col>
                            </v-row>
                          </v-container>
                        </v-card-text>

                        <v-card-actions>
                          <v-spacer></v-spacer>
                          <v-btn
                            color="blue-darken-1"
                            variant="text"
                            @click="close"
                          >
                            Cancel
                          </v-btn>
                          <v-btn
                            color="blue-darken-1"
                            variant="text"
                            @click="save"
                          >
                            Save
                          </v-btn>
                        </v-card-actions>
                      </v-card>
                    </v-dialog>
                    <v-dialog v-model="dialogDelete" max-width="500px">
                      <v-card>
                        <v-card-title class="text-h5"
                          >Are you sure you want to delete this
                          item?</v-card-title
                        >
                        <v-card-actions>
                          <v-spacer></v-spacer>
                          <v-btn
                            color="blue-darken-1"
                            variant="text"
                            @click="closeDelete"
                            >Cancel</v-btn
                          >
                          <v-btn
                            color="blue-darken-1"
                            variant="text"
                            @click="deleteItemConfirm"
                            >OK</v-btn
                          >
                          <v-spacer></v-spacer>
                        </v-card-actions>
                      </v-card>
                    </v-dialog>
                  </v-toolbar>
                </template>
                <template v-slot:item.actions="{ item }">
                  <v-icon size="small" class="me-2" @click="">
                    mdi-pencil
                  </v-icon>
                  <v-icon size="small" @click="">
                    mdi-delete
                  </v-icon>
                </template>
              </v-data-table>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-window-item>

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
