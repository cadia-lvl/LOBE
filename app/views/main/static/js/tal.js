var finalTranscription = '';
class TalWS {
    constructor(apiToken, audioCtx, stream, streamResultElem){
        finalTranscription = '';
        const source = audioCtx.createMediaStreamSource(stream);
        this.finalTranscription = '';
        let ws = new WebSocket(`wss://tal.ru.is/v1/speech:streamingrecognize?token=${apiToken}`, );
        ws.onopen = function(e) {
            ws.send(JSON.stringify({
                streamingConfig: {
                    config: {
                        sampleRate: audioCtx.sampleRate,
                        encoding:"LINEAR16",
                        maxAlternatives: 1 },
                interimResults: true}
            }));
            streamProcessor = audioCtx.createScriptProcessor(1024, 1, 1);
            source.connect(streamProcessor);
            streamProcessor.connect(audioCtx.destination);
            streamProcessor.onaudioprocess = function(e){
                if (!e.inputBuffer.getChannelData(0).every(
                    function(elem) { return elem === 0; })) {
                    var buffer = new ArrayBuffer(e.inputBuffer.length * 2);
                    var view = new DataView(buffer);
                    floatTo16BitPCM(view, 0, e.inputBuffer.getChannelData(0));
                    var encodedContent = base64ArrayBuffer(buffer);
                    ws.send(JSON.stringify({ audioContent: encodedContent }));
                }
            }
        };

        ws.onmessage = function(event){
            var response = JSON.parse(event.data);
            var result = response.result;
            var res = result.results;
            if (res !== undefined && res.length > 0) {
                if (res[0].isFinal) {
                    var transcript = res[0].alternatives[0].transcript || "";
                    finalTranscription = `${finalTranscription}${transcript}`;
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
                    streamResultElem.innerHTML = '';
                }
            }
        }
        this.ws = ws;
    }

    close(){
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ audioContent: "" }));
        }
    }

    getFinalTranscription(){
        return finalTranscription;
    }
}

// TODO: This is not finished
async function transcribeRecording(blobs, apiToken){
    let url = 'https://tal.ru.is/v1/speech:syncrecognize';
    let response = await fetch(url, {
        method: 'POST',
        headers: { bearer: apiToken},
        body:{
            config: {
                encoding: "LINEAR16",
                languageCode: "is-IS",
                sampleRate: 16000,
                wordAlignment: true,
                maxAlternatives: 1
              },
              audio: {
                content: blobs
            }
        }
    });

    let result = await response.json();
    console.log(result);
}


function floatTo16BitPCM(output, offset, input) {
    for (var i = 0; i < input.length; i++, offset += 2) {
        var s = Math.max(-1, Math.min(1, input[i]));
        output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
}