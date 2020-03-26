function createMediaRecorder(options, stream, constraints){
    try {
        mediaRecorder = new MediaRecorder(stream, options);
        var settings = mediaRecorder.stream.getAudioTracks()[0].getSettings();
    } catch (e) {
        promptError("Villa kom upp við að búa til MediaRecorder. Líklega röng media constraints",
            e.message, e.stack);
    }

    mediaRecorder.onstop = (event) => {
        tokenCard.style.borderWidth = '1px';
        tokenCard.classList.remove('border-warning', 'border-success');
        skipButton.disabled = false;
        nextButton.disabled = false;
        prevButton.disabled = false;
        recordButtonText.innerHTML = 'Byrja';
    };

    mediaRecorder.ondataavailable = handleDataAvailable;
    function handleDataAvailable(event) {
        if (event.data && event.data.size > 0) {
            recordedBlobs.push(event.data);
        }
    }
    return mediaRecorder, settings;
}

function testMediaRecorder(options, stream, constraints){
    try {
        mediaRecorder = new MediaRecorder(stream, options, constraints);
    } catch (e) {
        console.log(`Villa kom upp við að búa til MediaRecorder. Líklega röng media constraints, ${e.message}, ${e.stack}`);
    }
    var audiotrack = mediaRecorder.stream.getAudioTracks()[0];
    var audioConstraints = audiotrack.getConstraints();
    var audioSettings = audiotrack.getSettings();
    var audioCapabilities = audiotrack.getCapabilities();
    var results = {};
    for(var key in constraints.audio){
        console.log(key);
        results[key] = {
            capability: audioCapabilities[key],
            constraint: audioConstraints[key],
            setting: audioSettings[key],
            success: audioConstraints[key] == audioSettings[key]
        }
    }
    var mimeTypeInfo = {
        constraint: options.mimeType,
        success: MediaRecorder.isTypeSupported(options.mimeType)
    };

    stream.getTracks().forEach(track => track.stop());

    return [results, mimeTypeInfo];
}