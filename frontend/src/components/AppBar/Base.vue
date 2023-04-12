<script setup>
import { ref, inject } from "vue"
import RomMIcon from '@/components/AppBar/RomMIcon.vue'
import PlatformsBtn from '@/components/AppBar/PlatformsBtn.vue'
import SearchBar from '@/components/AppBar/SearchBar.vue'
import SettingsBtn from '@/components/AppBar/SettingsBtn.vue'
import UploadBtn from '@/components/AppBar/UploadBtn.vue'

// Props
const selectedPlatform = ref('')
const scanning = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('selectedPlatform', (p) => { selectedPlatform.value = p })
emitter.on('scanning', (s) => { scanning.value = s })
</script>

<template>

    <v-app-bar class="elevation-3">

        <v-progress-linear
            :active="scanning"
            :indeterminate="true"
            absolute/>
        
        <rom-m-icon/>

        <platforms-btn :selectedPlatform="selectedPlatform.slug"/>

        <v-spacer class="hidden-xs-and-down"/>
        
        <upload-btn/>

        <search-bar/>
        
        <template v-slot:append>
            <settings-btn/>
        </template>
        
    </v-app-bar>

</template>
