import axios from 'axios'
import { saveAs } from 'file-saver'


export function downloadRom(rom, emitter) {
    console.log("Downloading "+rom.file_name)
    emitter.emit('snackbarScan', {'msg': "Gathering "+rom.file_name+"...", 'icon': 'mdi-download', 'color': 'green'})
    emitter.emit('downloadingRom', true)
    axios.get('/assets'+rom.file_path+'/'+rom.file_name, { responseType: 'blob' }).then(response => {
        emitter.emit('downloadingRom', false, rom.file_name)
        emitter.emit('snackbarScan', {'msg': "Downloading "+rom.file_name, 'icon': 'mdi-download', 'color': 'green'})
        saveAs(new Blob([response.data], { type: 'application/file' }), rom.file_name)
    }).catch((error) => {
        emitter.emit('downloadingRom', false)
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't download "+rom.file_name+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
}

export function downloadSave(rom, emitter) {
    console.log("Downloading "+rom.file_name+" save file")
}
