# Large High Quality TTS Datasets
These recordings were captured as a part of the T1 project of the language technology program. When completed, this dataset will contain 8 voices diverse in age, gender and dialect. We record approximately 20 hours of speech data with each voice.

## Relationship to other projects
### Reading List
The reading list was generated mainly from the Gigacorpus, further details are available in [this paper](https://languageandvoice.files.wordpress.com/2020/05/sigurgeirsson2020sltuccurl-manual_speech_synthesis_data_aquisition.pdf). The 20 hour reading list generated contains 14400 unique sentences that were selected to maximize diphone coverage while minimizing sentence length. This list covers 81% of diphones at least 20 times. The list is available [here](https://github.com/cadia-lvl/tts_data/blob/master/reading_lists/rl_20hours.txt).

### LOBE
All recordings were captured in [LOBE](https://github.com/cadia-lvl/lobe), our in-house recording client.

## Technical details
### Recordings
By default, the recordings are captured at 44.1K-48KHz with 16-32 bit sample size. It is not guaranteed that all samples are captured in the same way as some of the earlier recordings were captured with a different recording stack. The recordings start and end with approximately 1 second of silence

### Corpus structure
Each directory in this datasets corresponds to one _collection_. Here, a collection is a mapping between sentences and voice recordings. Each collection has the following structure:
```
collection_id/
    audio/
        speaker_id/
            <wav_id_1>.wav
            <wav_id_2>.wav
            ...
    text/
        <sentence_id_1>.token
        <sentence_id_2>.token
        ...
    index.tsv
    info.json
    meta.json
```
* `index.tsv`: A direct mapping from sentences to recordings where each line is e.g.: `<speaker_id>\t<wav_id>.wav\t<sentence_id>.token`
* `info.json`: This file contains detailed information about each recording in the collection. An example object is shown below

    ```
    "6258": { // The recording id
            "collection_info": {
                "user_name": "n/a",
                "user_id": 27,
                "session_id": 132
            },
            "text_info": {
                "id": 7182,
                "fname": "new_000007182.token",
                "score": 1.0, // Dictates in what order the sentences are read, higher score means read earlier in collection
                "text": "Samtals urðu greinar hans átján, allar markaðar fágætu innsæi og víðtækri þekkingu.",
                "pron": "s a m t a l s\tʏ r ð ʏ\tk r eiː n a r\th a n s\tauː t j au n\ta t l a r\tm a r̥ k a ð a r\tf auː c ai t ʏ\tɪ n s ai j ɪ\tɔː ɣ\tv i ð t ai k r ɪ\tθ ɛ h c i ŋ k ʏ" // the pronounciation is split on words with a \t delimiter
            },
            "recording_info": {
                "recording_fname": "2019-12-10T113456.682Z_r000006258.wav",
                "sr": 44100,
                "num_channels": 1,
                "bit_depth": 16,
                "duration": 8.5449433106576
            },
            "other": {
                "transcription": "",
                "recording_marked_bad": false, //A user has marked this recording as bad in some way
                "text_marked_bad": false //A user has marked this sentence as bad in some way
            }
        },
    ```
* `meta.json`: Contains information about this collection and the speakers involved. An example file is shown below.
    ```
    {
        "speakers": [
            {
                "id": 27,
                "name": "n/a",
                "email": "n/a",
                "sex": female,
                "age": 50,
                "dialect": "n/a"
            }
        ],
        "collection": {
            "id": 7,
            "name": "n/a",
            "assigned_user_id": 27
        }
    }
    ```