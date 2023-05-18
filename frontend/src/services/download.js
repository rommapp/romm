import JSZip from "jszip"
import { saveAs } from 'file-saver'
import { storeDownloading } from '@/stores/downloading.js'

const downloading = storeDownloading()

export async function downloadRom(rom, emitter, filesToDownload=[]) {
    downloading.add(rom.file_name)
    emitter.emit('snackbarShow', {msg: `Downloading ${rom.file_name}...`, icon: 'mdi-download', color: 'green'})
    if(rom.multi){
        const zip = new JSZip()
        var zipFilename = `${rom.file_name}.zip`
        var files = []
        filesToDownload.forEach(f => {files.push(f)})
        if (files.length == 0){ files = rom.files }
        var count = 0
        files.forEach(async function (file_part) {
            var file_full_path = `/assets/romm/library/${rom.file_path}/${rom.file_name}/${file_part}`
            var file = await fetch(file_full_path)
            var fileBlob = await file.blob()
            var f = zip.folder(rom.file_name);
            f.file(file_part, fileBlob, { binary: true });
            count ++
            if (count == files.length) { zip.generateAsync({ type: 'blob' }).then(function (content) { saveAs(content, zipFilename); }); }
        })
    }
    else{
        var file_full_path = `/assets/romm/library/${rom.file_path}/${rom.file_name}`
        var file = await fetch(file_full_path)
        var fileBlob = await file.blob()
        saveAs(fileBlob, rom.file_name)
    }
    downloading.remove(rom.file_name)
}

export async function downloadSave(rom) { console.log(`Downloading ${rom.file_name} save file`) }
