from __future__ import division

import obspython as obs
import requests, json 
from selenium import webdriver
from urllib.parse import urlsplit
import time

import asyncio
import datetime
import random
import websockets
from websocket import create_connection
import re
import sys

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio

from six.moves import queue

#This is the audio recording parameters
RATE = 16000
CHUNK = int(RATE/10) #100ms

apiClientID = ""
twitchUsername = ""
source_name = ""
broadcaster_id = ""
access_token = ""
clipEditURL = ""
clipID = None
chromeDriverPath = ""
chromeProfilePath = ""
responses = ""
transcript = ""


#------------------------------------------------------------
#This is the audio recording parameters
RATE = 16000
CHUNK = int(RATE/10) #100ms

class MicrophoneStream(object):
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        #we create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        print("enter me daddy")
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(format=pyaudio.paInt16, channels=1, rate=self._rate,input=True,
        frames_per_buffer=self._chunk, stream_callback=self._fill_buffer,
        )

        self.closed= False

        return self

    def __exit__(self, type, value, traceback):
        print("this is being called")
        # self._audio_stream.stop_stream()
        # self._audio_stream.close()
        # # self.closed = True
        # #clear the buffer
        # self._buff.put(None)
        # #close the PyAudio interface
        # self._audio_interface.terminate()


    def _fill_buffer(self, in_data, frame_count,time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            #use get to make sure that there is at least one chunk of audio
            #that can be used to transcribe, and if chunk == None then that
            #means that the audio stream is done
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b''.join(data)

def listen_print_loop():
    global responses
    global transcript
    global clipID
    """
    recognized_text = "Transcribed text: \n"
    for response in responses:
        for index in range(len(response['results'])):
            recognized_text += response['results'][i]['alternatives'][0]['transcript']

    """
    if(clipID is not None):
        print("fuck me")
        ws = create_connection("ws://127.0.0.1:5678/")
        ws.send(clipID)
        ws.close()
        clipID = None

    try:   
        response=responses.next()
    except StopIteration:
        print("Stopped Iteration")
        return
    #print("Response: ", response, " in a list of ", responses)
    #interim_results = [response for response in responses]
    #print(interim_results)
    result = response.results[0]
    # print(response)
    # print("\nResult: ", result.alternatives)
    if not result.alternatives:
        return

    transcript = result.alternatives[0].transcript
    #print(result.alternatives)
    print("Transcript: ", transcript)
    update_text()
    if ("clip" in transcript or "clips" in transcript or
        "cliff" in transcript or "put"  in transcript):
        print("Word: CLIP DETECTED")
        createClip()
    # print("Iteration #: ", counter)
    # counter += 1
    #overwrite_chars = ' ' *  (num_chars_printed - len(transcript))
   
def main():
    print("HI IM MAIN")
    global responses
    language_code= 'en-US'

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,language_code = language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config, interim_results=False)


    with MicrophoneStream(RATE,CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        obs.timer_add(listen_print_loop, 300)





# ------------------------------------------------------------
def getBroadcasterID():
	global broadcaster_id
	getURL = "https://api.twitch.tv/helix/users?login=" + twitchUsername
	response = requests.get(getURL, headers={"Client-ID": apiClientID})
	responsedata = response.json()
	broadcaster_id = responsedata["data"][0]["id"]
	print("Broadcaster ID:", broadcaster_id)
    
def authenticate():
	print("Preparing to Authenticate")
	global access_token
	options = webdriver.ChromeOptions()
	optionsArgument = "user-data-dir="+chromeProfilePath
	options.add_argument(optionsArgument)
	driver = webdriver.Chrome(executable_path = chromeDriverPath, chrome_options = options)
	url = "https://id.twitch.tv/oauth2/authorize?response_type=token&client_id="+apiClientID+"&redirect_uri=http://localhost:8080&scope=clips:edit&state=c3ab8aa609ea12e793ae92361f002671"
	driver.get(url)
	dirtyBit = 1
	while(dirtyBit == 1):
		url = driver.current_url
		if("#access_token" in url):
				dirtyBit = 0
		else:
				pass

	parsedURL = urlsplit(url)
	urlFragments = parsedURL.fragment
	urlFragments = urlFragments.split("&")
	access_token = urlFragments[0].split("=")[1]
	driver.close()
	print("Successfully Authenticated, Grabbed Bearer Token")

def createClip():
    global clipEditURL
    global clipID
    headerElm = "Bearer " + access_token
    postURL = "https://api.twitch.tv/helix/clips?broadcaster_id=" + broadcaster_id
    response = requests.post(postURL, headers={"Authorization" : headerElm})
    responsedata = response.json()
    if("error" in responsedata):
    	print("WARNING ERROR:", responsedata["error"], responsedata["message"])
    else:
        clipEditURL = responsedata["data"][0]["edit_url"]
        clipID = responsedata["data"][0]["id"]

        print("Clip Edit URL:", clipEditURL)

def openClipEdit():
	if(clipEditURL):
		print("Opening webpage to edit clip")
		options = webdriver.ChromeOptions()
		optionsArgument = "user-data-dir="+chromeProfilePath
		options.add_argument(optionsArgument)
		driver = webdriver.Chrome(executable_path = chromeDriverPath, chrome_options = options)
		driver.get(clipEditURL)
		#How to close window after
	else:
		print("There is no clip to edit")

def update_text():
    global source_name

	#Changes source text to clipped text
    source = obs.obs_get_source_by_name(source_name)
    text = transcript
    if source is not None:
        settings = obs.obs_data_create()
        obs.obs_data_set_string(settings, "text", text)
        obs.obs_source_update(source, settings)
        obs.obs_data_release(settings)
        obs.obs_source_release(source)
	#Once clipped how does the text disapear?

def clip_pressed(props, prop):
	print("Clip button pressed")
	createClip()

def start_pressed(pros, prop):
    print("Start button pressed")
    getBroadcasterID()
    authenticate()
    main()
    # start_server = websockets.serve(main, "127.0.0.1", 5678)
    # print("crashing")

    # asyncio.get_event_loop().run_until_complete(start_server)
    # asyncio.get_event_loop().run_forever()



def clipedit_pressed(pros, prop):
	print("Clip Edit button pressed")
	openClipEdit()




# ------------------------------------------------------------

def script_description():
	return "Never miss a moment! AutoClip automatically creates Twitch clips/instant replays through voice recognition to showcase on stream."

def script_update(settings):
	global apiClientID
	global twitchUsername
	global source_name
	global chromeDriverPath
	global chromeProfilePath

	apiClientID      = obs.obs_data_get_string(settings, "apiClientID")
	twitchUsername   = obs.obs_data_get_string(settings, "twitchUsername")
	source_name 	 = obs.obs_data_get_string(settings, "source")
	chromeDriverPath = obs.obs_data_get_string(settings, "chromeDriverPath")
	chromeProfilePath= obs.obs_data_get_string(settings, "chromeProfilePath")

def script_properties():
	props = obs.obs_properties_create()

	obs.obs_properties_add_button(props, "button1", "Start", start_pressed)
	
	obs.obs_properties_add_button(props, "button2", "Clip Now", clip_pressed)

	obs.obs_properties_add_button(props, "button3", "Edit Last Clip", clipedit_pressed)

	p = obs.obs_properties_add_list(props, "source", "CC Text Source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
	sources = obs.obs_enum_sources()
	if sources is not None:
		for source in sources:
			source_id = obs.obs_source_get_id(source)
			if source_id == "text_gdiplus" or source_id == "text_ft2_source":
				name = obs.obs_source_get_name(source)
				obs.obs_property_list_add_string(p, name, name)

		obs.source_list_release(sources)

	obs.obs_properties_add_text(props, "twitchUsername", "Twitch Username", obs.OBS_TEXT_DEFAULT)

	obs.obs_properties_add_text(props, "apiClientID", "API Client ID", obs.OBS_TEXT_DEFAULT)

	obs.obs_properties_add_text(props, "chromeDriverPath", "Chrome Driver Path", obs.OBS_TEXT_DEFAULT)

	obs.obs_properties_add_text(props, "chromeProfilePath", "Chrome Profile Path", obs.OBS_TEXT_DEFAULT)


	return props
