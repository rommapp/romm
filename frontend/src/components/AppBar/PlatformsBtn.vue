<script setup>
import { inject } from "vue"

// Props
const props = defineProps(['selectedPlatform'])

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-btn
        @click="emitter.emit('platformsDrawer')"
        class="ma-4 hidden-lg-and-up"
        rounded="0"
        icon>
        <v-avatar rounded="0">
            <v-img :src="'/assets/platforms/'+selectedPlatform+'.ico'"/>
        </v-avatar>
    </v-btn>
</template>