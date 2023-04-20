<script setup>
import { inject } from "vue"

// Event listeners bus
const emitter = inject('emitter')

</script>

<template>
    <v-btn
        @click="emitter.emit('togglePlatforms')"
        rounded="0"
        icon
    >
        <v-avatar rounded="0">
            <v-img v-if="$route.params.platform !== undefined" :src="'/assets/platforms/'+$route.params.platform+'.ico'"/>
            <v-icon v-else icon="mdi-menu"/>
        </v-avatar>
    </v-btn>
</template>