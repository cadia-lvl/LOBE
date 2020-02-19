function createWaveSurfer(playButtonIcon, container){
    wavesurfer =  WaveSurfer.create({
        container: container,
        waveColor: '#00bc8c',
        cursorColor: '#F39C12',
    });

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

function createMicSurfer(context, container){
    wavesurfer =  WaveSurfer.create({
        container: container,
        waveColor: '#00bc8c',
        cursorWidth: 0,
        audioContext: context,
        audioScriptProcessor: context.createScriptProcessor(1024, 1, 1),
        plugins: [
            WaveSurfer.microphone.create({})
        ]
    });

    return wavesurfer;
}