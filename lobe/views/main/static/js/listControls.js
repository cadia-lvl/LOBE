var isPlaying = false;
var currentId;
var audio;
var playButtonIcon;

function play(id){
    if(isPlaying){
        //stop
        isPlaying = false;
        playButtonIcon.removeClass('fa-stop').addClass('fa-play');
        audio.pause();
        audio.currentTime = 0;
        // play the other clip if another id was chosen
        if(id !== currentId){
            play(id);
        }
    } else{
        //start
        //isPlaying = true;
        currentId = id;
        playButtonIcon = $("#playButtonIcon-"+id);
        audio = document.getElementById('audio-'+id);
        // set listeners
        audio.onplaying = function(){
            isPlaying = true;
        }
        audio.onpause = function(){
            isPlaying = false;
        }
        audio.onended = function(){
            playButtonIcon.removeClass('fa-stop').addClass('fa-play');
        }
        // play audio
        playButtonIcon.removeClass('fa-play').addClass('fa-stop');
        audio.play();
    }
}

function toggle_recording_bad(url, id){
    $.get(url, function(data, status){
        console.log(data);
        console.log(data=='True');
        if(data=='True'){
            $('#'+id+"-name").removeClass('text-success').addClass('text-warning');
            $('#'+id+"-btn").removeClass('text-warning').addClass('text-success');
            $('#'+id+"-btn").html('<span class="mr-2"><i class="fa fa-check"></i></span>Merkja sem góð');
            console.log($('#'+id+"-btn"));
        } else{
            $('#'+id+"-name").removeClass('text-warning').addClass('text-success');
            $('#'+id+"-btn").removeClass('text-success').addClass('text-warning');
            $('#'+id+"-btn").html('<span class="mr-2"><i class="fa fa-times"></i></span>Merkja sem léleg');
        }
    });
}
