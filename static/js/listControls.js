
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