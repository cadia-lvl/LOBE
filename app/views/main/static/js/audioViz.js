(function(Peaks) {
    var options = {
        /** REQUIRED OPTIONS **/
        // Containing element: either
        container: document.getElementById('peaks-container'),

        // or (preferred):
        //containers: {
        //  zoomview: document.getElementById('zoomview-container'),
        //  overview: document.getElementById('overview-container')
        //},

        // HTML5 Media element containing an audio track
        mediaElement: document.querySelector('audio'),

        // If true, Peaks.js will send credentials with all network requests,
        // i.e., when fetching waveform data.
        withCredentials: false,

        webAudio: {
          // A Web Audio AudioContext instance which can be used
          // to render the waveform if dataUri is not provided
          audioContext: new AudioContext(),

          // Alternatively, provide an AudioBuffer containing the decoded audio
          // samples. In this case, an AudioContext is not needed
          audioBuffer: null,

          // If true, the waveform will show all available channels.
          // If false, the audio is shown as a single channel waveform.
          multiChannel: false
        },

        // async logging function
        logger: console.error.bind(console),

        // if true, emit cue events on the Peaks instance (see Cue Events)
        emitCueEvents: false,

        // default height of the waveform canvases in pixels
        height: 200,

        // Array of zoom levels in samples per pixel (big >> small)
        zoomLevel: [512, 1024, 2048, 4096],

        // Bind keyboard controls
        keyboard: false,

        // Keyboard nudge increment in seconds (left arrow/right arrow)
        nudgeIncrement: 0.01,

        // Colour for the in marker of segments
        inMarkerColor: '#a0a0a0',

        // Colour for the out marker of segments
        outMarkerColor: '#a0a0a0',

        // Colour for the zoomed in waveform
        zoomWaveformColor: 'rgba(0, 225, 128, 1)',

        // Colour for the overview waveform
        overviewWaveformColor: 'rgba(0,0,0,0.2)',

        // Colour for the overview waveform rectangle
        // that shows what the zoom view shows
        overviewHighlightColor: 'grey',

        // The default number of pixels from the top and bottom of the canvas
        // that the overviewHighlight takes up
        overviewHighlightOffset: 11,

        // Colour for segments on the waveform
        segmentColor: 'rgba(255, 161, 39, 1)',

        // Colour of the play head
        playheadColor: 'rgba(0, 0, 0, 1)',

        // Colour of the play head text
        playheadTextColor: '#aaa',

        // Show current time next to the play head
        // (zoom view only)
        showPlayheadTime: false,

        // the color of a point marker
        pointMarkerColor: '#FF0000',

        // Colour of the axis gridlines
        axisGridlineColor: '#ccc',

        // Colour of the axis labels
        axisLabelColor: '#aaa',

        // Random colour per segment (overrides segmentColor)
        randomizeSegmentColor: true,

        // Array of initial segment objects with startTime and
        // endTime in seconds and a boolean for editable.
        // See below.
        segments: [{
          startTime: 120,
          endTime: 140,
          editable: true,
          color: "#ff0000",
          labelText: "My label"
        },
        {
          startTime: 220,
          endTime: 240,
          editable: false,
          color: "#00ff00",
          labelText: "My Second label"
        }],

        // Array of initial point objects
        points: [{
          time: 150,
          editable: true,
          color: "#00ff00",
          labelText: "A point"
        },
        {
          time: 160,
          editable: true,
          color: "#00ff00",
          labelText: "Another point"
        }]
      }

    Peaks.init(options, function(err, peaks) {
        console.log(peaks.player.getCurrentTime());
    });
  })(peaks);