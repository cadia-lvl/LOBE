function analyzeAudio(recordedBlobs, postURL, conf){
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
    fd.append("audio", blob, 'analyze.webm');
    fd.append("top_db", conf.trim_threshold);
    fd.append("low_thresh", conf.low_threshold);
    fd.append("high_thresh", conf.high_threshold);
    fd.append("high_frames", conf.high_frames);

    var xhr = new XMLHttpRequest();
    xhr.onload = function(e){
        if(this.readyState === XMLHttpRequest.DONE) {
            if(xhr.status == '200'){
                msg = xhr.responseText;
            } else{
                promptError('Villa kom upp við að greina hljóðskrá', xhr.responseText);
                msg = "error";
            }
        }
    }
    xhr.open('POST', postURL, false);
    xhr.send(fd);
    return msg;
}