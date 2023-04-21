<script setup>
import { ref, inject } from "vue"
import SettingsHeader from '@/components/SettingsDrawer/Header.vue'

import SettingsFooter from '@/components/SettingsDrawer/Footer.vue'

// Props
const settingsDrawer = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('toggleSettings', () => { settingsDrawer.value = !settingsDrawer.value })
</script>

<template>

    <v-navigation-drawer
        v-model="settingsDrawer"
        location="right"
        width="270"
        class="bg-secondary"
        temporary
        floating>
        
        <settings-header class="bg-primary"/>

        <v-divider class="border-opacity-100" :thickness="2"/>
        
        <template v-slot:append>
            <v-divider class="border-opacity-25"/>
            <theme-toggle/>
            <v-divider class="border-opacity-25"/>
            <settings-footer class="bg-primary"/>
        </template>

    </v-navigation-drawer>
</template>
