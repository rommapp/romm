export const views = {
    0:{'view': 'small', 'icon': 'mdi-view-module', 'size-lg': 1, 'size-md': 2, 'size-sm': 2, 'size-xs': 3, 'size-cols': 4},
    1:{'view': 'big', 'icon': 'mdi-view-list', 'size-lg': 2, 'size-md': 3, 'size-sm': 3, 'size-xs': 6, 'size-cols': 6},
    2:{'view': 'list', 'icon': 'mdi-view-comfy', 'size-lg': 1, 'size-md': 2, 'size-sm': 2, 'size-xs': 3, 'size-cols': 4}
}

export function normalizeString(s) { return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,"") }
