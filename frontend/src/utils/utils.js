import JSZip from "jszip"
import { saveAs } from 'file-saver'


export async function downloadRom(rom, emitter) {
    console.log("Downloading "+rom.file_name)
    emitter.emit('snackbarScan', {'msg': "Downloading "+rom.file_name+"...", 'icon': 'mdi-download', 'color': 'green'})
    if(rom.multi){
        var zipFilename = rom.file_name+".zip"
        const zip = new JSZip()
        var count = 0;
        rom.files.forEach(async function (file_part) {
            var file_full_path = "/assets"+rom.file_path+"/"+rom.file_name+"/"+file_part
            console.log(file_full_path)
            var file = await fetch(file_full_path)
            var fileBlob = await file.blob()
            var f = zip.folder(rom.file_name);
            f.file(file_part, fileBlob, { binary: true });
            count ++
            if (count == rom.files.length) {
                zip.generateAsync({ type: 'blob' }).then(function (content) {
                    saveAs(content, zipFilename);
                });
            }
        })
    }
    else{
        var file_full_path = "/assets"+rom.file_path+"/"+rom.file_name
        var file = await fetch(file_full_path)
        var fileBlob = await file.blob()
        saveAs(fileBlob, rom.file_name)
    }
}

export async function downloadSave(rom, emitter) {
    console.log("Downloading "+rom.file_name+" save file")
}
