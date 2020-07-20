
var isPlaying = false; //Is playback ongoing?
var recordingIndex = 0;
var numRecordings = recordings.length;

//setup UI
updateUI();

$(window).keydown(function (e) {
	if (e.keyCode === 38 || e.keyCode === 87) {
        prevAction();
    } else if(e.keyCode === 37 || e.keyCode === 65){
		//prevAction();
	} else if(e.keyCode === 39 || e.keyCode === 68){
		//prevAction();
	} else if(e.keyCode === 40 || e.keyCode === 83){
		nextAction();
	}
});

function nextAction(){
    /**
     * If an audio file is not playing and we are not at
     * the last recorindg
     */
    if(!isPlaying && recordingIndex < numRecordings - 1){
        recordingIndex += 1;
        updateUI();
    }
}

function prevAction(){
    /**
     * If an audio file is not playing and we are not at
     * the first recording
     */
    if(!isPlaying && recordingIndex > 0){
        recordingIndex -= 1;
        updateUI();
    }
}

function updateUI(){
    updateTableUI();
}

function updateTableUI(){
    console.log(recordingIndex + 1);
    /**
     * Adds the highlight to the current row
     */
    $('.rate-row').each(function(){
        $(this).removeClass('table-active font-weight-bold');
    })

    var currentRow = $('#row-'+(recordingIndex+1));
    currentRow.addClass('table-secondary font-weight-bold');
    $("body").scrollTop(currentRow);
}