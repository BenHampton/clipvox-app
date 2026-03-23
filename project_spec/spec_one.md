create a python app that creates a video in the format best suited for uploading to youtube shorts, tictocks and facebook reels. here is a list of requirements:

Config:
- configs should be pulled from a json file called config.json

Background video requirements:
- I want there to be a background video for the app video
- background video should have a parent value in the config.json called "backgroundVideo" and the rest of the background video config values should be a child of this
- it should be pulled from background_videos directory, the video name should be used from the config.json and defaulted with the current existing .mp4 file
- it should use the defined video from the config
- it should create a new 1 min clip from the selected background video from a random spot
- any background music should be removed
- it should save these clips to be used later
- it should save the clips in a dir under background_videos called "clips"
- the saved clip name should come form the config.json and defaulted with "saved_clip_" if a saved clip was created and the config values was empty
- the saved clips should use the config name and append the current datetime it was created
- there should be a config value to determine if the background video should create a new clip or use an existing clipd from the saved clips.

Talk to speak (tts) requirements:
- i want to add tts to the background video
- tts should have a parent value in the config.json called "tts" and the rest of the tts values should be a child of this
- i will be using elevenlabs for tts
- there should be config options elevenlabs for the API key, default model and default voice.
- the default api key should be "API_KEY"
- the default modal should be "eleven_multilingual_v2"
- the default voice should be "JBFqnCBsd6RMkjVDRZzb"
- the value passed to elevenlabs should be a path to a string array that select a random option
- the default config value for the path should be "talk_to_speak/hannibal_lecter/phrases.json"
- this path should be added to the config and if empty throw an error
- save the elevenlabs response to be used for later
- there should be a config option to determine if a saved elevenlabs response should be used
- if the saved elevenlabs response should be used do not make a request to elevenlabs
- the saved elevenlabs response should be added to the talk_to_speak directory and the dir path should be added to the config, if the dir does not exist create the dir
- if the config option is empty then default the dir "talk_to_speak/saved_elevenlabs_tts"
- the saved filed name should be the "tts_elevenlabs_" and the current datetime appended to it. there should be a config option to add a optional prefix which is defaulted to empty
- tts text should be centered in the middle of the video
- the tts text should be colored white and clear to read
- the font and color should be added to the config
- the tts text should display the words at the same time as they are spoken
- the speed of the words should be calculated based of the saved elevenlabs response
- tts text should display a few words at a time depending on the length of the words in the sentence