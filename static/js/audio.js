window.onbeforeunload = function() {
    return "Are you sure?";
 };

URL = window.URL || window.webkitURL;

var startTime = new Date();
var recordWaitTime = 1;
var gumStream;
var rec;
var input;

var AudioContext = window.AudioContext || window.webkitAudioContext;
var audioContext;
var streamProcessor;
var sampleRate;
var ws; // the websocket for stream recognition

var tokenIndex = 0; //At what token are we now?
var isRecording = false; //Is the microphone active?
var isPlaying = false; //Is playback ongoing?
var numTokens = tokens.length;

/** ----------------- DOM elements ----------------- */

var streamResultElem = document.getElementById("transcription");
var finalTranscriptionElem = $("#finalTrupdateTableUIanscription");

var tokenText = $("#tokenText");
var tokenIDSpan = $("#tokenID");
var tokenHref= $("#tokenHref");
var tokenfileIDSpan = $("#tokenFileID");
var tokenProgress = $('#tokenProgress');
var currentIndexSpan = $('#currentIndexSpan');
var totalIndexSpan = $('#totalIndexSpan');
var playerListItem = $('#playerListItem');
var transcriptionListItem = $('#transcriptionListItem');

var recordingIDSpan = $('#recordingIDSpan');
var recordingPlayer = document.getElementById('recordingPlayer');
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
finishButton.attr('disabled',true);
var finishButtonIcon = $('#finishButtonIcon');
var skipButton = $('#skipButton');

var volumeBar = $('#volumeBar');
var WIDTH=500;
var HEIGHT=50;

/** ----------------- Listeners ----------------- */

recordingPlayer.onplaying = function(){
	isPlaying = true;
}
recordingPlayer.onpause = function(){
	isPlaying = false;
}

recordingPlayer.onended = function(){
	playAction(isEnded=true);
}

nextButton.click(function(){nextAction()});
prevButton.click(function(){prevAction()});
playButton.click(function(){playAction()});
recordingDeleteButton.click(function(){deleteRecordAction()});
recordButton.click(function(){recordAction()});
finishButton.click(function(){sendAction()});
skipButton.click(function(){skipAction()});

$(window).keyup(function (e) {
	if (e.key === ' ' || e.key === 'Spacebar'  || e.keyCode === 38 || e.keyCode === 87) {
		// spacebar, arrow-up or "w"
		e.preventDefault()
		recordAction();
	} else if(e.keyCode === 37 || e.keyCode === 65){ // arrow-left or "a"
		prevAction();
	} else if(e.keyCode === 39 || e.keyCode === 68){ // arrow-right or "d"
		nextAction();
	} else if(e.keyCode === 40 || e.keyCode === 83){ // arrow-down or "s"
		playAction();
	}
});

/** ----------------- UI initialization ----------------- */

totalIndexSpan.text(numTokens)
updateUI(tokenIndex);

/** ----------------- UI functions ----------------- */

function setProgress(num){
	var ratio = (num / numTokens) * 100;
	tokenProgress.css({"width":ratio.toString()+"%"});
}

function setTokenUI(index){
	setProgress(index + 1);
	tokenText.text(tokens[index]['text']);
	tokenIDSpan.text(tokens[index]['id']);
	tokenfileIDSpan.text(tokens[index]['file_id']);
	tokenHref.attr('href', tokens[index]['url'])
	currentIndexSpan.text(index + 1);
};

function setRecordingUI(index){
	/**
	If the current token has a recording:
	  	* Show filename of recording
	  	* Add the correct source to the media player
	  	* Populate the download link
	  	* Show the list item
	Else:
		* hide the list item
	 */
	if("recording" in tokens[index]){
		recording = tokens[index]['recording']
		recordingIDSpan.text(recording['filename']);
		recordingPlayer.setAttribute('src', recording['url']);
		recordingDownload.attr('href', recording['url']).attr('download', recording['filename']);
		playerListItem.show()
	} else{
		playerListItem.hide();
	}
};

function setTranscriptionUI(index){
	streamResultElem.innerHTML = '';
	if("recording" in tokens[index]){
		streamResultElem.innerHTML = tokens[index]['recording']['transcript'];
		transcriptionListItem.show();
	} else{
		streamResultElem.innerHTML = '';
		transcriptionListItem.hide();
	}
}

function initializeRecordButton(){
	recordButtonIcon.removeClass('fa-redo').addClass('fa-microphone')
	recordButton.attr('data-state', 'intial');
	recordButtonText.text('byrja');
}

function setDirectionButtonUI(index){
	prevButton.prop('disabled', false);
	nextButton.prop('disabled', false);

	if(index == 0){
		prevButton.prop("disabled", true);
	} else if(index == numTokens - 1){
		nextButton.prop("disabled", true);
	}
}

function setFinishButtonUI(){
	//only allow if at least one marked token or one recording
	for(var i=0; i<numTokens; i++){
		if('recording' in tokens[i] || tokens[i].skipped){
			finishButton.attr('disabled', false);
			return true;
		}
	}
	finishButton.attr('disabled', true);
}

function setSkipButtonUI(index){
	if(tokens[index].skipped){
		skipButton.removeClass('border-dark').addClass('border-danger');
		// also disable the recording button
		recordButton.attr('disabled', true);
	} else{
		skipButton.removeClass('border-danger').addClass('border-dark');
		recordButton.attr('disabled', false);
	}
}

function updateUI(index, updateRecBtn=true){
	setTokenUI(index);
	setRecordingUI(index);
	setTranscriptionUI(index);
	setDirectionButtonUI(index);
	setFinishButtonUI();
	setSkipButtonUI(index);
	if(updateRecBtn){
		initializeRecordButton();
	}
}

/** ----------------- Actions ----------------- */
function skipAction(){
	// mark as skipped
	if('skipped' in tokens[tokenIndex]){
		// reverse from marking as skipped
		delete tokens[tokenIndex].skipped;
		updateUI(tokenIndex);
	} else{
		tokens[tokenIndex].skipped = true;
		// then go to next
		if('recording' in tokens[tokenIndex]){
			delete tokens[tokenIndex].recording;
		}
		nextAction();
	}
}

function nextAction(){
	// are we playing or recording?
	if(!isRecording && !isPlaying){
		// are there any tokens next?
		if(tokenIndex < numTokens - 1){tokenIndex += 1; updateUI(tokenIndex);}
	}
};

function prevAction(){
	if(!isRecording && !isPlaying){
		if(tokenIndex > 0){ tokenIndex -= 1; updateUI(tokenIndex);}
	}
};

function playAction(isEnded=false){
	if(!isRecording && recordingPlayer.getAttribute('src') !== ''){
		if(isPlaying || isEnded){
			recordingPlayer.pause();
			recordingPlayer.currentTime = 0;
			playButtonIcon.removeClass('fa-stop').addClass('fa-play');
		} else{
			recordingPlayer.play();
			playButtonIcon.removeClass('fa-play').addClass('fa-stop');
		}
	}
}

function deleteRecordAction(){
	console.log(tokens[tokenIndex]);
	if('recording' in tokens[tokenIndex]){
		delete tokens[tokenIndex].recording;
		updateUI(tokenIndex);
	}
}

function recordAction(){
	if(recordButton.attr('data-state') == 'initial'){
		// delete any old recording if there is one
		deleteRecordAction();

		recordButtonIcon.removeClass('fa-microphone')
			.addClass('fa-spinner fa-spin')
		recordButton.attr('data-state', 'recording');
		recordButtonText.text('lesa');

		startRecording();
		updateUI(tokenIndex, updateRecBtn=false);

	} else if(recordButton.attr('data-state') == 'recording'){

		//pause for a period to avoid cutting the recording too early
		var timeleft = recordWaitTime;
		recordButtonText.text(timeleft);
		recordButton.removeClass('recording-button').addClass('pending-button');

		var recordTimer = setInterval(function(){
			timeleft -= 1;
			recordButtonText.text(timeleft);
			if(timeleft <= 0){
				recordButtonIcon.removeClass('fa-spinner fa-spin').addClass('fa-redo')
				recordButton.attr('data-state', 'done');
				recordButton.removeClass('pending-button');
				recordButtonText.text('aftur');
				clearInterval(recordTimer);
				stopRecording();
			}
		}, 1000);
		//updateUI(tokenIndex, updateRecBtn=false);

	} else {
		deleteRecordAction();
		isRecording = true; // added here to avoid switching while waiting
		var timeleft = recordWaitTime;
		recordButtonText.text(timeleft);
		recordButton.addClass('pending-button');

		var recordTimer = setInterval(function(){
			timeleft -= 1;
			recordButtonText.text(timeleft);
			if(timeleft <= 0){
				clearInterval(recordTimer);
				recordButtonIcon.removeClass('fa-redo x').addClass('fa-spinner fa-spin')
				recordButton.attr('data-state', 'recording');
				recordButton.removeClass('pending-button').addClass('recording-button')
				recordButtonText.text('lesa');
				startRecording();
				updateUI(tokenIndex, updateRecBtn=false);
			}
		}, 1000);
	}
}

function sendAction(){
	finishButtonIcon.removeClass('fa-arrow-right').addClass('fa-spinner').addClass('fa-spin');
	var xhr = new XMLHttpRequest();
	xhr.onload = function(e) {
		if(this.readyState === XMLHttpRequest.DONE) {
			finishButtonIcon.removeClass('fa-spinner').removeClass('fa-spin');
			if(xhr.status == '200'){
				var session_url = xhr.responseText;
				finishButtonIcon.addClass('fa-check');
			} else{
				finishButtonIcon.addClass('fa-times');
				finishButton.addClass('btn-danger');
				alert("Something went wrong when submitting the recordings."+
					" Please try again by either pressing the 'meira' button "+
					"below or by refreshing this page. Send this error to admins:\n"+
					xhr.responseText);
			}
		}
		finishButton.attr('disabled',true);
	};
	var fd = new FormData();
	for(var i=0; i<numTokens; i++){
		if('recording' in tokens[i]){
			fd.append(tokens[i]['id'], JSON.stringify(tokens[i]['recording']));
			fd.append("file_"+tokens[i]['id'], tokens[i]['recording']['blob'], tokens[i]['recording']['filename']);
		} else if(tokens[i].skipped){
			// append as skipped
			fd.append(tokens[i]['id'], JSON.stringify('skipped'));
		}
	}
	// append duration to the form
	var endTime = new Date()
	var duration = (endTime.getTime() - startTime.getTime())/1000;
	fd.append('duration', JSON.stringify(duration));
	xhr.open("POST", postRecordingRoute, true);
	xhr.send(fd);
}

/** ----------------- Recording Functions ----------------- */

function startRecording() {
	isRecording = true;
	navigator.mediaDevices.getUserMedia({audio:true, video:false}).then(function(stream) {
		audioContext = new AudioContext();
		meter = createAudioMeter(audioContext);
		sampleRate = audioContext.sampleRate;
		gumStream = stream;

		input = audioContext.createMediaStreamSource(stream);
		input.connect(meter);
		analyser = audioContext.createAnalyser();
		analyser.fftsize = 1024;
		input.connect(analyser)

		rec = new Recorder(input,{numChannels:2})
		rec.record();

		ws = new WebSocket("wss://tal.ru.is/v1/speech:streamingrecognize?token=" + talAPIToken, );
		ws.onopen = function(e) {
			ws.send(JSON.stringify({
				streamingConfig: {
					config: { sampleRate: sampleRate, encoding:"LINEAR16",
						maxAlternatives: 1 },
				interimResults: true}
			}));
		};

		ws.onmessage = handleStreamingResult;

		streamProcessor = audioContext.createScriptProcessor(16384, 1, 1);
		input.connect(streamProcessor);
		streamProcessor.connect(audioContext.destination);

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
		onLevelChange();
	})}

function onLevelChange(time){
	if(isRecording){
		if(meter.checkClipping()){
			volumeBar.removeClass('bg-success').addClass('bg-warning');
		} else{
			volumeBar.removeClass('bg-warning').addClass('bg-success');
		}
		volumeBar.css({"width":(meter.volume*200).toString()+"%"});
		rafID = window.requestAnimationFrame( onLevelChange );
	} else{
		volumeBar.css({"width": "0%"})
	}
}

function stopRecording() {
	//tell the recorder to stop the recording
	rec.stop();
	//stop microphone access
	gumStream.getAudioTracks()[0].stop();
	//create the wav blob and pass it on to createDownloadLink
	rec.exportWAV(createAudioFile);

	isRecording = false;
}

function createAudioFile(blob) {
	var url = URL.createObjectURL(blob);
	//name of .wav file to use during upload and download (without extendion)
	var filename = new Date().toISOString();
	// add recording to token
	tokens[tokenIndex]['recording'] = {
		'filename':filename + '.wav',
		'url': url,
		'blob': blob}

	// submit to WS one last time to confirm end of recording,
	// then add the transcription to the token. Also update the
	// UI, finally.
	if (!!ws) {
		if (ws.readyState === WebSocket.OPEN) {
			ws.send(JSON.stringify({ audioContent: "" }));
		}
	}
}

/** ----------------- Transcribing Functions ----------------- */

function handleStreamingResult(event) {
	var response = JSON.parse(event.data);
	var result = response.result;
	var res = result.results;
	if (res !== undefined && res.length > 0) {
		transcriptionListItem.show();
		if (res[0].isFinal) {
			var transcript = res[0].alternatives[0].transcript || "";
			var segmentId = "streamingResult-" + (result.resultIndex || 0);
			var segmentSpan = document.getElementById(segmentId);
			if (!segmentSpan) {
				segmentSpan = document.createElement("span");
				segmentSpan.id = segmentId;
				segmentSpan.innerHTML = transcript;
				streamResultElem.appendChild(segmentSpan);
			} else {
				segmentSpan.innerHTML = transcript;
				segmentSpan.classList.remove("streaming-result-interim");
			}
			segmentSpan.classList.add("streaming-result-final");
		} else if (res[0] !== undefined){
			var transcript = res[0].alternatives[0].transcript || "";
			var segmentId = "streamingResult-" + (result.resultIndex || 0);
			var segmentSpan = document.getElementById(segmentId);
			if (!segmentSpan) {
				segmentSpan = document.createElement("span");
				segmentSpan.id = segmentId;
				segmentSpan.classList.add("streaming-result-interim");
				segmentSpan.innerHTML = transcript;
				streamResultElem.appendChild(segmentSpan);
			} else {
				segmentSpan.innerHTML = transcript;
			}
		}
	} else{
		if(result.endpointerType === "END_OF_AUDIO"){
			var spans = streamResultElem.children;
			var transcript = ''
			for(var i=0; i< spans.length; i++){
				transcript += spans[i].innerHTML;
			}
			if(transcript === ''){
				transcript = 'Ekkert til afritunar';
			}
			tokens[tokenIndex]['recording']['transcript'] = transcript;
			updateUI(tokenIndex, updateRecBtn=false);
		}
	}
}

function floatTo16BitPCM(output, offset, input) {
	for (var i = 0; i < input.length; i++, offset += 2) {
	var s = Math.max(-1, Math.min(1, input[i]));
	output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
	}
}

function wait(ms){
	var start = new Date().getTime();
	var end = start;
	while(end < start + ms) {
	  end = new Date().getTime();
   }
 }
