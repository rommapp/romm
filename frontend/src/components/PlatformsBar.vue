<script>
import axios from 'axios'
export default {
    data() {
        return {
            server: "asgard",
            port: "5000",
            currentPlatform: "",
            platformsLoaded: false,
            scaning: false
        };
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
        },
        getPlatformsSlug(slug) {
            console.log(slug+' selected!')
            this.currentPlatform = slug
        }
    }
}
</script>

<template>
    
    <v-navigation-drawer theme="dark" width="250" >
        <v-list>
            <v-list-item prepend-icon="mdi mdi-controller">Rom Manager</v-list-item>
        </v-list>

        <vdvider class="text-white"></vdvider>

        <v-list nav v-if="platformsLoaded">
            <v-list-item v-for="platform in platforms"
                :title="platform.name" 
                :value="platform.slug" 
                :key="platform.slug" 
                v-on:click="getPlatformsSlug(platform.slug)"/>
        </v-list>
    </v-navigation-drawer>

</template>
