<script setup>
import axios from 'axios'
import { ref } from "vue";
import { useTheme } from "vuetify";

const server = "localhost"
const port = "5000"

const platforms = ref([])
console.log("Getting platforms...")
const GetPlatforms = async () => {
    await axios.get('http://'+server+':'+port+'/platforms').then((response) => {
        console.log("Platforms loaded!")
        console.log(response.data.data)
        platforms.value = response.data.data
    })
}
GetPlatforms()

const scanOverwrite = ref(false)
const scan = async () => {
    await axios.get('http://'+server+':'+port+'/scan?overwrite='+scanOverwrite.value).then((response) => {
        console.log("scan completed")
        console.log(response.data)
        GetPlatforms()
    })
}

const theme = useTheme();
const darkMode = (localStorage.getItem('theme') == 'dark') ? ref(true) : ref(false)
const toggleTheme = () => {
    theme.global.name.value = darkMode.value ? "dark" : "light"
    darkMode.value ? localStorage.setItem('theme', 'dark') : localStorage.setItem('theme', 'light')
}

</script>

<template>
    
    <v-navigation-drawer width="250" permanent>
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider ></v-divider>

        <v-list nav>
            <v-list-item v-for="platform in platforms" 
                :title="platform.name" 
                :value="platform.slug"
                :key="platform"
                @:click="$emit('currentPlatform', platform.slug)"/>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-row>
                <div class="font-weight-bold d-flex align-center justify-center fill-height ml-3">
                    <v-col>
                        <v-btn color="secondary" prepend-icon="mdi mdi-magnify-scan" @click="scan()" inset >Scan</v-btn>
                    </v-col>
                    <v-col class="font-weight-bold d-flex align-center justify-center ml-3">
                        <v-checkbox v-model="scanOverwrite" label="Full"></v-checkbox>
                    </v-col>
                </div>
            </v-row>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <div class="font-weight-bold d-flex align-center justify-center fill-height">
                <v-switch prepend-icon="mdi mdi-brightness-6" v-model="darkMode" @change="toggleTheme()" inset class="ml-3"/>
            </div>
        </v-list>

    </v-navigation-drawer>

</template>
