function createMeter(audioCtx, stream){
    var meter = createAudioMeter(audioCtx, 0.98, 0, 200);
    var mediaStreamSource = audioCtx.createMediaStreamSource(stream);
    mediaStreamSource.connect(meter);
    return meter;
}


function meterDrawLoop(time){
    // clear the background
    canvasContext.clearRect(0,0, meterCanvas.width, meterCanvas.height);

    // check if we're currently clipping
    if (meter.checkClipping())
        canvasContext.fillStyle = "#E74C3C";
    else
        canvasContext.fillStyle = "#00bc8c";

    // draw a bar based on the current volume
    canvasContext.fillRect(0, 0, meter.volume*meterCanvas.width*1.4, meterCanvas.height);

    // set up the next visual callback
    rafID = window.requestAnimationFrame( meterDrawLoop );
}
