make the following updates:
- update the config and move apiKey to a .env file that will be added to the .gitignore so it will never be checked in
- the saved tts response from elevenlabs that gets saved under talk_to_speak/saved_elevenlabs_tts
- group the related json and mp4 files under a newly created dir
- name the dir the same as the file
- move dir to the parent of the phrases.json
- remove the config for savedTtsDir
- confirm the saved_elevenlabs_tts should be nested under the parent of the configured phrases.json
- when the tts is added to the video use multiple tts to fill up the entire video with 1.5 second inbetween tts clips

### Claude's questions
● Done. Added talk_to_speak/saved_elevenlabs_tts/, results/, and background_videos/ to .gitignore.

❯ Use the requirements in project_spec/spec_two.md to generate the code.                                                                                                                         
ask me questions one at a time be for creating the application                                                                                                                                   
                                                                                                                                                                                                 
Read 1 file (ctrl+o to expand)                                                         
● Let me read the existing code to understand the current state before asking questions.                                                                                                         
              
Read 4 files (ctrl+o to expand)       
● I've read all the relevant files. Here's my first question:

For the "multiple TTS to fill up the entire video" feature — currently the video duration is capped at 60 seconds. Should the app keep picking random phrases (with 1.5s gaps between them) and
 repeat until the full video duration is filled, or should there be a fixed number of TTS clips per video?                                                                                     
                                                                                                                                                                                               
❯ lets bring that time doen to 0.5 sec inbetween them and it should pick a new one based of the time left to fill for the video. it should also not repeat the same tts for the current video    
                    
Got it — 0.5s gaps, no repeats within a single video run, fill based on time remaining.                                                                                                        
  

Next question: When useSavedTts is true and there are already saved TTS clips — should the app reuse those existing saved clips to fill the video (generating new ones only when it runs out of
 saved clips), or should it always generate fresh TTS clips each run and just save them for potential future reuse?                                                                            
                                                                                                                                                                                               
❯ always follow what the config values are. so if useSavedTts is true it should use the saved clips and not fetch new ones, if there was more than 15 seconds left that were not filled with tts 
then log a clear warning                                                                                                      


● Understood. Next question:    

When useSavedTts is true but there aren't enough saved clips to fill the video — should it use whatever saved clips exist (even if they leave >15s unfilled and log the warning), or should it 
fall back to calling the ElevenLabs API for the remaining phrases?
                                                                                                                                                                                               
❯ should it use whatever saved clips exist (even if they leave >15s unfilled and log the warning)                                                                                                
                                                                                                
● Got it. Next question:                                                                                                                                                                         
                                       
For the new folder structure — the spec says to group each TTS pair (mp3 + json) into a subdirectory named after the file, nested under the parent of phrases.json. So for                     
talk_to_speak/hannibal_lecter/phrases.json, saved clips would live at:
                                                                                                                                                                                               
```
talk_to_speak/hannibal_lecter/saved_elevenlabs_tts/       
  tts_elevenlabs_20260321_220741/
    tts_elevenlabs_20260321_220741.mp3
    tts_elevenlabs_20260321_220741.json

```

Does that match your expectation?

❯ yes                                                                                                                                                                                            
    
● Good. Last question:                                                                                                                                                
For the video duration — when filling the video with multiple TTS clips, should the video length be driven by the background clip's duration (i.e. fit as many TTS clips as possible within the
 existing clip length), or should the video be extended/trimmed to exactly fit however many TTS clips were loaded?                                                                             
                                                                                                                                                                                               
❯ the video be extended/trimmed to exactly fit however many TTS clips  were loaded but do not go trim  under 45 sec or extend over 1min                                                          
        

I have everything I need. Let me read the remaining files before coding.        


## Moving files 

 the saved_elevenlabs_tts file did not get grouped like expected. move the folder to the same level as the file defined by phrasesPath config value and group the related json and mp4 with a   
new dir name of the file name.                                                                                                                                                                   
  ⎿  ⧉ Selected 1 lines from ..\..\..\..\..\..\mnt\c\Users\benja\Documents\git\Python\clipvox-app\project_spec\sepc_two.md in PyCharm

● Let me check what currently exists on disk.

  Searched for 1 pattern (ctrl+o to expand)

● I can see the issue — existing files are flat in the old talk_to_speak/saved_elevenlabs_tts/ location. I need to move them to talk_to_speak/hannibal_lecter/saved_elevenlabs_tts/ and group
  each pair into its own subdirectory.

● Bash(cd "C:/Users/benja/Documents/git/Python/clipvox-app" && \
      NEW_BASE="talk_to_speak/hannibal_lecter/saved_elevenlabs_tts" && \…)
  ⎿  Interrupted · What should Claude do instead?

❯ the saved_elevenlabs_tts file did not get grouped like expected. move the folder to the same level as the file defined by phrasesPath config value and group the related json and mp4 with a   
new dir name of the file name. this should also be updated when saving new tts files and follow the same pattern.  ask me questions one at a time before doing the updates                       

● Should I also migrate the existing flat files in talk_to_speak/saved_elevenlabs_tts/ into the new grouped structure under talk_to_speak/hannibal_lecter/saved_elevenlabs_tts/, or only update
  the code so new files follow the new pattern going forward?

❯ both                                                                                                                                                                                           

● Got it. The new target structure would be:

```
  talk_to_speak/hannibal_lecter/
    phrases.json
    saved_elevenlabs_tts/
      tts_elevenlabs_20260321_220315/
        tts_elevenlabs_20260321_220315.mp3
        tts_elevenlabs_20260321_220315.json
```

  After migrating, should the old talk_to_speak/saved_elevenlabs_tts/ folder be deleted?

❯ no i will manually delete it                                                                                                                                                                   

● One more: the .gitignore currently ignores the old path talk_to_speak/saved_elevenlabs_tts/. Should I update it to **/saved_elevenlabs_tts/ so it covers the new location (and any future
  phrase sets)?

❯ yes                                                                                                                                                                                            

● Now I have everything I need. Let me make all the changes.

● Bash(cd "C:/Users/benja/Documents/git/Python/clipvox-app" && \
      NEW_BASE="talk_to_speak/hannibal_lecter/saved_elevenlabs_tts" && \…)
  ⎿  Moved tts_elevenlabs_20260321_220315
     Moved tts_elevenlabs_20260322_210030
     Moved tts_elevenlabs_20260322_211438
     … +6 lines (ctrl+o to expand)
                                                                                                                                                                                                 
● Now update .gitignore:
                                                                                                                                                                                                 
● Update(.gitignore)                                                                                                                                                                             
  ⎿  Added 1 line, removed 1 line                                                                                                                                                                
      113  Thumbs.db                                                                                                                                                                             
      114                                                                                                                                                                                      
      115  # Project-specific generated files                                                                                                                                                    
      116 -talk_to_speak/saved_elevenlabs_tts/                                                                                                                                                 
      116 +**/saved_elevenlabs_tts/                                                                                                                                                              
      117  results/                                                                                                                                                                            
      118  background_videos/
      119  

● Let me verify the new structure looks right:

  Searched for 1 pattern (ctrl+o to expand)                                                                                                                                                      
   
● All 8 clips migrated correctly. Here's what was done:                                                                                                                                          
                                                                                                                                                                                               
  - Migrated all 8 existing flat files from talk_to_speak/saved_elevenlabs_tts/ into grouped subdirs at talk_to_speak/hannibal_lecter/saved_elevenlabs_tts/{name}/{name}.mp3|.json               
  - .gitignore updated from talk_to_speak/saved_elevenlabs_tts/ → **/saved_elevenlabs_tts/ to cover the new location and any future phrase sets
  - The code in tts_generator.py already derives the save path from phrasesPath and creates the grouped structure, so new files will follow the same pattern automatically                       
                                                            
  You can manually delete the now-empty talk_to_speak/saved_elevenlabs_tts/ folder when ready.

