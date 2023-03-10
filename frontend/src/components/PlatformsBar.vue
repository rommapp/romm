<script>
import axios from 'axios'
export default {
    data() {
        return {
            server: "localhost",
            port: "5000",
            platforms: [],
            platformsLoaded: false,
            scaning: false,
        }
    },
    created() {
        console.log("Getting platforms...")
        axios.get('http://'+this.server+':'+this.port+'/platforms').then((response) => {
            console.log("Platforms loaded!")
            console.log(response.data)
            this.platforms = response.data.data
            this.platformsLoaded = true
        })
    },
    methods: {
        scan(overwrite) {
            this.scaning = true
            axios.get('http://'+this.server+':'+this.port+'/scan?overwrite='+overwrite).then((response) => {
                console.log("scan completed")
                console.log(response.data)
                this.scaning = false
            })
        }
    }
}
</script>

<template>
    
    <v-navigation-drawer width="250">
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <v-divider ></v-divider>

        <v-list nav >
            <v-list-item v-for="platform in platforms"
                :title="platform.name" 
                :value="platform.slug" 
                :is="platform.slug" 
                @:click="$emit('currentPlatform', platform.slug)"/>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-btn color="secondary" prepend-icon="mdi mdi-magnify-scan" @click="scan()" inset class="ml-3">Scan</v-btn>
        </v-list>

        <v-divider ></v-divider>

        <v-list>
            <v-switch prepend-icon="mdi mdi-brightness-6" inset class="pl-3"/>
        </v-list>

    </v-navigation-drawer>

</template>
