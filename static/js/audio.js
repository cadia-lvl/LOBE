URL = window.URL || window.webkitURL;

var gumStream;
var rec;
var input;

var AudioContext = window.AudioContext || window.webkitAudioContext;
var audioContext

var tokenIndex = 0;
var numTokens = tokens.length;
var tokenText = $("#tokenText");
var tokenIDSpan = $("#tokenID");
var tokenfileIDSpan = $("#tokenFileID");
var tokenProgress = $('#tokenProgress');
var currentIndexSpan = $('#currentIndexSpan');
var totalIndexSpan = $('#totalIndexSpan');
var recordingInfoList = $('#recordingInfoList');
var playerListItem = $('#playerListItem');

var recordingIDSpan = $('#recordingIDSpan');
var recordingPlayer = $('#recordingPlayer');
var htmlRecordingPlayer = document.getElementById('recordingPlayer');
var isPlaying = false;
htmlRecordingPlayer.onplaying = function(){
	isPlaying = true;
}
htmlRecordingPlayer.onpause = function(){
	isPlaying = false;
}
htmlRecordingPlayer.onended = function(){
	playAction(isEnded=true);
}



var recordingDownload = $('#recordingDownload');
var recordingDeleteButton = $('#recordingDeleteButton');

var recordButton = $("#recordButton");
var recordButtonText = $('#recordButtonText');
var recordButtonIcon = $('#recordButtonIcon');

var playButton = $('#playButton');
var playButtonIcon = $('#playButtonIcon');


var prevButton = $('#prevButton');
var nextButton = $('#nextButton');

var finishButton = $('#finishButton');
var finishButtonIcon = $('#finishButtonIcon');

function setProgress(num){
	var ratio = (num / numTokens) * 100;
	tokenProgress.css({"width":ratio.toString()+"%"});
}

function setTokenUI(index){
	setProgress(index + 1);
	tokenText.text(tokens[index]['text']);
	tokenIDSpan.text(tokens[index]['id']);
	tokenfileIDSpan.text(tokens[index]['file_id']);
	currentIndexSpan.text(index + 1);

	prevButton.prop('disabled', false);
	nextButton.prop('disabled', false);

	if(index == 0){
		prevButton.prop("disabled", true);
	} else if(index == numTokens - 1){
		nextButton.prop("disabled", true);
	}
};

function setRecordingUI(index){
	if("recording" in tokens[index]){
		recording = tokens[index]['recording']
		recordingIDSpan.text(recording['filename']);
		recordingPlayer.attr('src', recording['url']);
		recordingDownload.attr('href', recording['url']).attr('download', recording['filename']);
		recordingInfoList.show();

	} else{
		recordingInfoList.hide();
	}
};

function updateUI(index, updateRecBtn=true){
	setTokenUI(index);
	setRecordingUI(index);
	if(updateRecBtn){
		initializeRecordButton();
	}
}

// set up some UI elements that use the tokens object
totalIndexSpan.text(numTokens)
updateUI(tokenIndex);

$(window).keyup(function (e) {
	if (e.key === ' ' || e.key === 'Spacebar'  || e.keyCode === 38 || e.keyCode === 87) {
		e.preventDefault()
		recordAction();
	} else if(e.keyCode === 37 || e.keyCode === 65){
		prevAction();
	} else if(e.keyCode === 39 || e.keyCode === 68){
		nextAction();
	} else if(e.keyCode === 40 || e.keyCode === 83){
		playAction();
	}
});

nextButton.click(function(){nextAction()});
function nextAction(){
	if(tokenIndex < numTokens - 1){
		tokenIndex += 1;
		updateUI(tokenIndex);
	}
};

prevButton.click(function(){prevAction()});
function prevAction(){
	if(tokenIndex > 0){
		tokenIndex -= 1;
		updateUI(tokenIndex);
	}
};


playButton.click(function(){playAction()});
function playAction(isEnded=false){
	console.log(htmlRecordingPlayer.duration);
	console.log(htmlRecordingPlayer.paused);
	console.log(htmlRecordingPlayer.currentTime);

	if(isPlaying || isEnded){
		htmlRecordingPlayer.pause();
		htmlRecordingPlayer.currentTime = 0;
		playButtonIcon.removeClass('fa-stop').addClass('fa-play');
	} else{
		htmlRecordingPlayer.play();
		playButtonIcon.removeClass('fa-play').addClass('fa-stop');

	}
}

recordingDeleteButton.click(function(){deleteRecordAction()});
function deleteRecordAction(){
	delete tokens[tokenIndex].recording;
	updateUI(tokenIndex);
}

recordButton.click(function(){recordAction()});
function recordAction(){
	if(recordButton.attr('data-state') == 'initial'){
		recordButtonIcon.removeClass('fa-microphone')
			.addClass('fa-spinner').addClass('fa-spin')
		recordButton.attr('data-state', 'recording');
		recordButtonText.text('lesa');

		startRecording();

	} else if(recordButton.attr('data-state') == 'recording'){
		recordButtonIcon.removeClass('fa-spinner')
		.removeClass('fa-spin').addClass('fa-repeat')
		recordButton.attr('data-state', 'done');
		recordButtonText.text('aftur');

		stopRecording();

	} else {
		recordButtonIcon.removeClass('fa-repeat')
		.addClass('fa-spinner').addClass('fa-spin')
		recordButton.attr('data-state', 'recording');
		recordButtonText.text('lesa');

		startRecording();
	}
	updateUI(tokenIndex, updateRecBtn=false);
}

function initializeRecordButton(){
	recordButtonIcon.removeClass('fa-repeat').addClass('fa-microphone')
	recordButton.attr('data-state', 'intial');
	recordButtonText.text('byrja');
}


function startRecording() {
    var constraints = { audio: true, video:false }

	navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
		audioContext = new AudioContext();

		gumStream = stream;

		input = audioContext.createMediaStreamSource(stream);
		analyser = audioContext.createAnalyser();
		analyser.fftsize = 1024;
		input.connect(analyser)

		rec = new Recorder(input,{numChannels:2})
		rec.record()
	})}

function stopRecording() {
	//tell the recorder to stop the recording
	rec.stop();

	//stop microphone access
	gumStream.getAudioTracks()[0].stop();

	//create the wav blob and pass it on to createDownloadLink
	rec.exportWAV(createAudioFile);
}

function createAudioFile(blob) {
	var url = URL.createObjectURL(blob);
	var au = document.createElement('audio');
	var li = document.createElement('li');
	var link = document.createElement('a');

	//name of .wav file to use during upload and download (without extendion)
	var filename = new Date().toISOString();

	//add controls to the <audio> element
	au.controls = true;
	au.src = url;

	//save to disk link
	link.href = url;
	link.download = filename+".wav"; //download forces the browser to donwload the file using the  filename
	link.innerHTML = "Save to disk";

	//add the new audio element to li
	li.appendChild(au);

	//add the save to disk link to li
	li.appendChild(link);

	//upload link
	var upload = document.createElement('a');
	upload.href="#";
	upload.innerHTML = "Upload";
	upload.addEventListener("click", function(event){
		  var xhr=new XMLHttpRequest();
		  xhr.onload = function(e) {
		      if(this.readyState === 4) {
		          console.log("Server returned: ",e.target.responseText);
		      }
		  };
		  var fd = new FormData();
		  fd.append('token', $("#token_id").val())
		  fd.append("file", blob, filename);
		  xhr.open("POST","/post_recording", true);
		  xhr.send(fd);
	})
	li.appendChild(document.createTextNode (" "))//add a space in between
	li.appendChild(upload)//add the upload link to li

	//add the li element to the ol
	//playerListItem.append(li);

	addRecordingToToken(tokenIndex, filename+'.wav', url, audioContext.sampleRate, blob);

	// this is needed here for async reasons
	updateUI(tokenIndex, updateRecBtn=false);
}

function addRecordingToToken(index, filename, url, sr, blob){
	tokens[index]['recording'] = {
		'filename':filename,
		'url': url,
		'sample_rate':sr,
		'blob': blob
	}
}

finishButton.click(function(){sendForm()});
function sendForm(){
	finishButtonIcon.removeClass('fa-arrow-right').addClass('fa-spinner').addClass('fa-spin');


	var xhr = new XMLHttpRequest();
	xhr.onload = function(e) {
		if(this.readyState === 4) {
			finishButtonIcon.removeClass('fa-spinner').removeClass('fa-spin').addClass('fa-check');
		}
	};
	var fd = new FormData();
	for(var i=0; i<numTokens; i++){
		if('recording' in tokens[i]){
			fd.append('token_'+tokens[i]['id'], tokens[i]['id']);
			fd.append("file_"+tokens[i]['id'], tokens[i]['recording']['blob'], tokens[i]['recording']['filename']);
		}
	}
	xhr.open("POST","/post_recording", true);
	xhr.send(fd);
}

