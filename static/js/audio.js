URL = window.URL || window.webkitURL;

var gumStream;
var rec;
var input;

var AudioContext = window.AudioContext || window.webkitAudioContext;
var audioContext;
var streamProcessor;
var sampleRate;

var tokenIndex = 0;
var numTokens = tokens.length;

var streamingRecognizeResultsElem = document.getElementById(
	"transcription");

var tokenText = $("#tokenText");
var tokenIDSpan = $("#tokenID");
var tokenfileIDSpan = $("#tokenFileID");
var tokenProgress = $('#tokenProgress');
var currentIndexSpan = $('#currentIndexSpan');
var totalIndexSpan = $('#totalIndexSpan');
var recordingInfoList = $('#recordingInfoList');
var playerListItem = $('#playerListItem');
var transcriptionListItem = $('#transcriptionListItem');

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
		playerListItem.show()
	} else{
		playerListItem.hide();
	}
};

function setTranscriptionUI(index){
	if("recording" in tokens[index]){
		streamingRecognizeResultsElem.innerHTML = tokens[index]['recording']['transcript'];
		transcriptionListItem.show();
	} else{
		streamingRecognizeResultsElem.innerHTML = '';
		transcriptionListItem.hide();
	}
}

function updateUI(index, updateRecBtn=true){
	setTokenUI(index);
	setRecordingUI(index);
	setTranscriptionUI(index);
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
		updateUI(tokenIndex, updateRecBtn=false);

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
		updateUI(tokenIndex, updateRecBtn=false);
	}
}

function initializeRecordButton(){
	recordButtonIcon.removeClass('fa-repeat').addClass('fa-microphone')
	recordButton.attr('data-state', 'intial');
	recordButtonText.text('byrja');
}

function startRecording() {
	navigator.mediaDevices.getUserMedia({audio:true, video:false}).then(function(stream) {
		audioContext = new AudioContext();
		sampleRate = audioContext.sampleRate;

		gumStream = stream;

		input = audioContext.createMediaStreamSource(stream);
		analyser = audioContext.createAnalyser();
		analyser.fftsize = 1024;
		input.connect(analyser)

		rec = new Recorder(input,{numChannels:2})
		rec.record();


		streamProcessor = audioContext.createScriptProcessor(16384, 1, 1);
		input.connect(streamProcessor);
		streamProcessor.connect(audioContext.destination);

		ws = new WebSocket("wss://tal.ru.is/v1/speech:streamingrecognize?token=" + talAPIToken);

		ws.onopen = function(e) {
		ws.send(JSON.stringify({
			streamingConfig: {
			config: { sampleRate: sampleRate, encoding: "LINEAR16",
						maxAlternatives: 1 },
			interimResults: true
			}
		}));
		};
		ws.onmessage = handleStreamingResult;

		streamProcessor.onaudioprocess = function(e) {
		if (!e.inputBuffer.getChannelData(0).every(
			function(elem) { return elem === 0; })) {
			var buffer = new ArrayBuffer(e.inputBuffer.length * 2);
			var view = new DataView(buffer);
			floatTo16BitPCM(view, 0, e.inputBuffer.getChannelData(0));
			var encodedContent = base64ArrayBuffer(buffer);
			ws.send(JSON.stringify({ audioContent: encodedContent }));

		}
		};
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
	//name of .wav file to use during upload and download (without extendion)
	var filename = new Date().toISOString();
	var finalTranscript = getFinalTranscript();
	addRecordingToToken(tokenIndex, filename+'.wav', url, blob, finalTranscript);
}

function addRecordingToToken(index, filename, url, blob, transcript=''){
	tokens[index]['recording'] = {
		'filename':filename,
		'url': url,
		'blob': blob,
		'transcript': transcript
	}
}

function getFinalTranscript(){
	var spans = streamingRecognizeResultsElem.children;
	var transcript = ''
	for(var i=0; i< spans.length; i++){
		transcript += spans[i].innerHTML;
	}
	return transcript;
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
			fd.append(tokens[i]['id'], JSON.stringify(tokens[i]['recording']));
			fd.append("file_"+tokens[i]['id'], tokens[i]['recording']['blob'], tokens[i]['recording']['filename']);
		}
	}
	xhr.open("POST","/post_recording", true);
	xhr.send(fd);
}

// TRANSCRIBE STUFF
function handleStreamingResult(event) {
	var response = JSON.parse(event.data);
	var result = response.result;
	var res = result.results;
	if (res !== undefined && res.length > 0) {
		transcriptionListItem.show();
		if (res[0].isFinal) {
			var transcript = res[0].alternatives[0].transcript || "";
			var segmentId = "streamingResult-" + (result.resultIndex || 0) +
							"-";
			var segmentSpan = document.getElementById(segmentId);
			if (!segmentSpan) {
				segmentSpan = document.createElement("span");
				segmentSpan.id = segmentId;
				segmentSpan.innerHTML = transcript;
				streamingRecognizeResultsElem.appendChild(segmentSpan);
			} else {
				segmentSpan.innerHTML = transcript;
				segmentSpan.classList.remove("streaming-result-interim");
			}
			segmentSpan.classList.add("streaming-result-final");
		} else if (res[0] !== undefined){
			var transcript = res[0].alternatives[0].transcript || "";
			var segmentId = "streamingResult-" + (result.resultIndex || 0) +
							"-";
			var segmentSpan = document.getElementById(segmentId);
			if (!segmentSpan) {
				segmentSpan = document.createElement("span");
				segmentSpan.id = segmentId;
				segmentSpan.classList.add("streaming-result-interim");
				segmentSpan.innerHTML = transcript;
				streamingRecognizeResultsElem.appendChild(segmentSpan);
			} else {
				segmentSpan.innerHTML = transcript;
			}
		}
	}
}

function floatTo16BitPCM(output, offset, input) {
	for (var i = 0; i < input.length; i++, offset += 2) {
	var s = Math.max(-1, Math.min(1, input[i]));
	output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
	}
}

