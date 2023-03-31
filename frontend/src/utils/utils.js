import axios from 'axios'
import { saveAs } from 'file-saver'


export function downloadRom(rom) {
    console.log("Downloading "+rom.file_name)
    axios.get(rom.file_path+'/'+rom.file_name, { responseType: 'blob' }).then(response => {
        saveAs(new Blob([response.data], { type: 'application/file' }), rom.file_name)
    }).catch((error) => {console.log(error)})
}

export function downloadSave(rom) {
    console.log("Downloading "+rom.file_name+" save file")
}
