import axios from 'axios'
import { saveAs } from 'file-saver'


export function downloadRom(rom) {
    console.log("Downloading "+rom.filename)
    axios.get('/assets/library/'+rom.p_slug+'/roms/'+rom.filename, { responseType: 'blob' }).then(response => {
        saveAs(new Blob([response.data], { type: 'application/file' }), rom.filename)
    }).catch(console.error)
}

export function downloadSave(rom) {
    console.log("Downloading "+rom.filename+" save file")
}