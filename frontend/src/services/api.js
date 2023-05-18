import axios from 'axios'


export async function fetchPlatformsApi () {
    return axios.get('/api/platforms')
}

export async function fetchRomsApi (platform) {
    return axios.get(`/api/platforms/${platform}/roms`)
}

export async function fetchRomApi (platform, rom) {
    return axios.get(`/api/platforms/${platform}/roms/${rom}`)
}

export async function updateRomApi (rom, updatedRom) {
    return axios.patch(`/api/platforms/${rom.p_slug}/roms/${rom.id}`, { updatedRom: updatedRom })
}

export async function deleteRomApi (rom, deleteFromFs) {
    return axios.delete(`/api/platforms/${rom.p_slug}/roms/${rom.id}?filesystem=${deleteFromFs}`)
}

export async function searchRomApi (searchTerm, searchBy, rom) {
    return axios.put(`/api/search/roms/igdb?search_term=${searchTerm}&search_by=${searchBy}`, { rom: rom })
}
