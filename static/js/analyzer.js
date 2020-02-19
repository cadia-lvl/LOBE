function analyzeAudio(recordedBlobs, postURL){
    /**
     * Returns:
     *  * 'ok' if recording is ok
     *  * 'low' if recording is low
     *  * 'high' if recording is high
     *  * 'error' if any errors occur
     */
    const blob = new Blob(recordedBlobs, {type: 'audio/webm'});
    var msg = "";
    var fd = new FormData();
    fd.append("audio", blob, 'test.webm');
    var xhr = new XMLHttpRequest();
    xhr.onload = function(e){
        if(this.readyState === XMLHttpRequest.DONE) {
            if(xhr.status == '200'){
                var b =0;
                msg = xhr.responseText;
            } else{
                promptError('Villa kom upp við að greina hljóðskrá', xhr.responseText);
                msg = "error";
            }
        }
    }
    xhr.on
    xhr.open('POST', postURL, false)
    xhr.send(fd);
    return msg;
}