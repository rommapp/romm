import JSZip from "jszip"
import { saveAs } from 'file-saver'
import { storeDownloader } from '@/stores/downloader.js'

const downloader = storeDownloader()

export async function downloadRom(rom, emitter, filesToDownload=[]) {
    downloader.add(rom.file_name)
    emitter.emit('snackbarScan', {'msg': "Downloading "+rom.file_name+"...", 'icon': 'mdi-download', 'color': 'green'})
    if(rom.multi){
        const zip = new JSZip()
        var zipFilename = rom.file_name+".zip"
        var files = []
        filesToDownload.forEach(f => {files.push(f)})
        if (files.length == 0){ files = rom.files }
        var count = 0
        files.forEach(async function (file_part) {
            var file_full_path = "/assets"+rom.file_path+"/"+rom.file_name+"/"+file_part
            var file = await fetch(file_full_path)
            var fileBlob = await file.blob()
            var f = zip.folder(rom.file_name);
            f.file(file_part, fileBlob, { binary: true });
            count ++
            if (count == files.length) { zip.generateAsync({ type: 'blob' }).then(function (content) { saveAs(content, zipFilename); }); }
        })
    }
    else{
        var file_full_path = "/assets"+rom.file_path+"/"+rom.file_name
        var file = await fetch(file_full_path)
        var fileBlob = await file.blob()
        saveAs(fileBlob, rom.file_name)
    }
    await new Promise(r => setTimeout(r, 10000));
    downloader.remove(rom.file_name)
}

export async function downloadSave(rom) { console.log("Downloading "+rom.file_name+" save file") }