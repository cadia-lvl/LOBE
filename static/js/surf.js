function surfOptions(options){
    return {...{
        waveColor: '#00bc8c',
        height: 80,
        progressColor: '#00bc8c',
        cursorColor: '#F39C12'},
        ...options};
}

function createSimpleWaveSurfer(container, has_video, playButtonIcon){
    let options = {
        container:container,
        plugins: [
            WaveSurfer.regions.create({
                dragSelection: {slop: 5},
                color: "rgba(243, 156, 18, 0.1)"
            })]}
    if(has_video){
        options = {...options, ...{backend: 'MediaElement'}};
    }

    const wavesurfer =  WaveSurfer.create(surfOptions(options));

    wavesurfer.on('finish',function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
    });

    wavesurfer.on('play', function(){
        playButtonIcon.classList.remove('fa-play');
        playButtonIcon.classList.add('fa-pause');
    });

    wavesurfer.on('pause', function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
    });

    return wavesurfer;

}

function createWaveSurfer(container, has_video, playButtonIcon, nextButton, prevButton,
    recordButton, skipButton, deleteButton){
        let options = {
            container:container,
            plugins: [
                WaveSurfer.regions.create({
                    dragSelection: {slop: 5},
                    color: "rgba(243, 156, 18, 0.1)"
                })]};
        if(has_video){
            options = {...options, ...{backend: 'MediaElement'}};
        }
        wavesurfer =  WaveSurfer.create(surfOptions(options));

    wavesurfer.on('finish',function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
        nextButton.disabled = false;
        prevButton.disabled = false;
        recordButton.disabled = false;
        skipButton.disabled = false;
        deleteButton.disabled = false;
    });

    wavesurfer.on('play', function(){
        playButtonIcon.classList.remove('fa-play');
        playButtonIcon.classList.add('fa-pause');
        nextButton.disabled = true;
        prevButton.disabled = true;
        recordButton.disabled = true;
        skipButton.disabled = true;
        deleteButton.disabled = true;

    });

    wavesurfer.on('pause', function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
        nextButton.disabled = false;
        prevButton.disabled = false;
        recordButton.disabled = false;
        skipButton.disabled = false;
        deleteButton.disabled = false;
    });

    wavesurfer.on('region-created', function(){
        if(Object.keys(wavesurfer.regions.list).length > 0){
            delete tokens[tokenIndex].cut;
            wavesurfer.clearRegions();
            setCutUI(newRegion=true);
        }
        wavesurfer.clearRegions();
    })

    wavesurfer.on('region-update-end', function(){
        if(Object.keys(wavesurfer.regions.list).length > 0){
            delete tokens[tokenIndex].cut;
            setCutUI();
        }
    })

    if(has_video){
        wavesurfer.on('destroy', function(){
            //re-create the recorded video element
            recordedVideo = document.createElement('video');
            recordedVideo.setAttribute('id', 'recordedVideo');
            recordedVideo.setAttribute('playsinline', 'playsinline');
            recordedVideo.style.display = 'none';
            videoCard.appendChild(recordedVideo);
        });
    }

    return wavesurfer;
}

function createMicSurfer(context, container){
    wavesurfer =  WaveSurfer.create(surfOptions({
        container: container,
        cursorWidth: 0,
        audioContext: context,
        audioScriptProcessor: context.createScriptProcessor(1024, 1, 1),
        plugins: [
            WaveSurfer.microphone.create({}),
        ]}));
    return wavesurfer;
}

// wavesurfer specifically for the /recordings/<id> route
function createRecordWaveSurfer(container, has_video, playButtonIcon){
    let options = {
        container:container,
        plugins: [
            WaveSurfer.regions.create({
                dragSelection: {slop: 5},
                color: "rgba(243, 156, 18, 0.1)"
            })]}
    if(has_video){
        options = {...options, ...{backend: 'MediaElement'}};
    }

    const wavesurfer =  WaveSurfer.create(surfOptions(options));

    wavesurfer.on('finish',function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
    });

    wavesurfer.on('play', function(){
        playButtonIcon.classList.remove('fa-play');
        playButtonIcon.classList.add('fa-pause');
    });

    wavesurfer.on('pause', function(){
        playButtonIcon.classList.remove('fa-pause');
        playButtonIcon.classList.add('fa-play');
    });

    wavesurfer.on('region-created', function(){
        //if(Object.keys(wavesurfer.regions.list).length > 0){
        //    wavesurfer.clearRegions();
        //}
        //wavesurfer.clearRegions();
    })

    wavesurfer.on('region-update-end', function(){
    })

    wavesurfer.on('region-dblclick', function(region, event){
        region.remove();
    })

    return wavesurfer;

}