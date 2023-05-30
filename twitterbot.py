import os
import random
import requests
import time
import tweepy
import schedule
import json
import logging
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from requests_oauthlib import OAuth1Session
import openai
from datetime import datetime

# Configura el logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carga las claves desde config.json
with open('config.json') as f:
    keys = json.load(f)

# Configura la API de Twitter v1.1 para la subida de imágenes
auth = tweepy.OAuthHandler(keys['twitter']['api_key'], keys['twitter']['api_secret_key'])
auth.set_access_token(keys['twitter']['access_token'], keys['twitter']['access_token_secret'])
twitter_api_v1 = tweepy.API(auth)

# Configura la API de Azure
azure_client = ComputerVisionClient(keys['azure']['endpoint'], CognitiveServicesCredentials(keys['azure']['subscription_key']))

# Configura la API de ChatGPT
openai.api_key = (keys['openai_credentials']['api_key'])

# OAuth1Session para la autenticación OAuth 1.0a
twitter_oauth = OAuth1Session(keys['twitter']['api_key'],
                              client_secret=keys['twitter']['api_secret_key'],
                              resource_owner_key=keys['twitter']['access_token'],
                              resource_owner_secret=keys['twitter']['access_token_secret'])

# URL de la API de Twitter v2 para publicar un tweet
tweet_v2_url = "https://api.twitter.com/2/tweets"

# Lista de URLs
urls = [
    'https://source.unsplash.com/random/1920x1080/?nature-from-drone/',
    'https://source.unsplash.com/random/1920x1080/?from-drone/',
    'https://source.unsplash.com/random/1920x1080/?landscape-from-drone/',
    'https://source.unsplash.com/random/1920x1080/?sunset-from-drone/',
    'https://source.unsplash.com/random/1920x1080/?sea-from-drone/',
    'https://source.unsplash.com/random/1920x1080/?island-from-drone/'
]

def job():
    try:
        # Selecciona una URL aleatoria de la lista
        url = random.choice(urls)
        description = ""

        # Descarga la imagen
        file_path = "image.jpg"
        response = requests.get(url)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"Imagen descargada desde {url} y guardada como {file_path}")

        # Obtiene la descripción de la imagen de Azure
        azure_description = azure_client.describe_image_in_stream(open(file_path, 'rb')).captions[0].text
        logging.info(f"Descripción de la imagen obtenida de Azure: {azure_description}")
        chatgpt_prompt = f"Generate a very short, minimal and adjective description for the image based on nature and landscape: \"{azure_description}\""
        try:
            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": chatgpt_prompt}], max_tokens=20)
            if response['choices']:
                description = response['choices'][0]['message']['content']
            else:
                description = azure_description
            logging.info(f"Descripción de la imagen obtenida de ChatGPT: {description}")
        except Exception as chatgpt_error:
            logging.error(f"Error en la generación de la descripción por ChatGPT: {chatgpt_error}")
            description = azure_description

        # Sube la imagen a Twitter y obtén el ID de los medios
        res = twitter_api_v1.media_upload(file_path)
        media_ids = [res.media_id_string]
        logging.info(f"Imagen subida a Twitter con el ID de los medios: {media_ids[0]}")

        # Publica un tweet con el ID de los medios usando la API de Twitter v2
        payload = {"text": description, "media": {"media_ids": media_ids}}
        response = twitter_oauth.post(tweet_v2_url, json=payload)

        if response.status_code != 201:
            logging.error(f"Error al publicar el tweet: {response.text}")
        else:
            logging.info(f"Tweet publicado exitosamente con el ID de los medios: {media_ids[0]}")
    except Exception as e:
        logging.error(f"Error en el trabajo: {e}")

# Función para mostrar el tiempo restante en el terminal
def show_countdown():
    next_run = schedule.next_run()
    remaining_time = next_run - datetime.now()
    print(f"Próximo tweet en: {remaining_time}")

# Programa el trabajo para que se ejecute cada 4 horas
schedule.every(4).hours.do(job)

job()

# Ejecuta todos los trabajos programados
while True:
    schedule.run_pending()
    show_countdown()
    time.sleep(600)
