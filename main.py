#!/usr/bin/env python

from bs4 import BeautifulSoup
import html
import logging
import os
import re
import requests
import ollama
import pandas as pd
import dipzy as dz

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

LLM_CTX = {
    'llama3': 8000,
    'gemma2': 8000,
    'gemma2:2b': 8000,
    'mistral-nemo': 128000
}
YOUTUBE_URL = "https://www.youtube.com"


get_video_url = lambda video_id: f"{YOUTUBE_URL}/watch?v={video_id}"
get_channel_url = lambda channel: f"{YOUTUBE_URL}/@{channel}"

def get_newest_video(channel):
    # Get title and URL of newest video on channel
    channel_html = requests.get(get_channel_url(channel) + "/videos").text
    # Video information can be found in ytInitialData variable in embedded 
    # script. ytInitialData can be parsed as JSON object. 
    # Assumption: Latest video is the first title that matches regex. I.e.
    # videos are sorted with the latest first.
    title = re.search(
        '(?<="title":{"runs":\[{"text":").*?(?="})', channel_html
    ).group()
    video_id = re.search('(?<="videoId":").*?(?=")', channel_html).group()
    published_time = re.search(
        '(?<="publishedTimeText":{"simpleText":").*?(?="})', channel_html
    ).group()
    view_counts = re.search(
        '(?<="viewCountText":{"simpleText":").*?(?="})', channel_html
    ).group()
    
    return title, video_id, published_time, view_counts


def get_captions(video_id, language="en"):
    video_html = requests.get(get_video_url(video_id)).text
    caption_url = re.search(
        '(?<="captionTracks":\[{"baseUrl":").*?(?=")', video_html
    ).group()
    # replace unicode encodings
    caption_url = caption_url.replace("\\u0026", "&") 
    # corresponding lang of caption_url
    lang = re.search(
        '(?<="simpleText":").*?(?="})', video_html
    ).group()
    lang_code = re.search('(?<=lang=).*?$', caption_url).group()
    assert lang_code == language 
    captions_xml = requests.get(caption_url).text
    soup = BeautifulSoup(captions_xml, "xml")
    text_tags = soup.find_all("text")
    captions = ""
    for text_tag in text_tags:
        captions = captions + html.unescape(text_tag.text) + " "
    logger.info(f"Retrieved {lang} ({lang_code}) captions for video.")

    return captions


def summarise(text, model="llama3", num_ctx=8000):
    '''Summarise text using ollama served locally run LLM

    Assumption: Ollama is serving the specified model!
    '''
    reply_limit = 600 # +50% buffer
    if num_ctx > LLM_CTX[model]:
        raise ValueError("num_ctx exceeds context size of model!")
    pagesize = num_ctx - reply_limit
    # Use ollama to summarise text
    words = text.split()
    nwords = len(words)
    ntokens = nwords * 4 / 3
    if ntokens > num_ctx:
        nwords_page = int(pagesize * 3 / 4)
        pages = [
            " ".join(words[i:(i + nwords_page)])
            for i in range(0, nwords, nwords_page)
        ]
        logger.info((
            f"Text contains {int(ntokens)} tokens, exceeding context size! "
            f"Text divided into {len(pages)} pages containing {nwords_page} words."
        ))
        responses = []
        for page in pages:
            prompt = "Summarise the following text: " + page
            logger.info("Requesting ollama API...")
            responses.append(ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": num_ctx}
            ))
        contents = [r["message"]["content"] for r in responses]
        content = " ".join(contents)
        return summarise(content, model, num_ctx)
    else:
        prompt = "Summarise the following text: " + text
        logger.info("Requesting ollama API...")
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_ctx": num_ctx}
        )
        return response["message"]["content"]


if __name__ == "__main__":
    file = "data/latest_videos.csv"
    latest_videos = pd.read_csv(file, index_col=0)
    channels = latest_videos.index 

    telegram_token = os.environ["TELEGRAM_TOKEN"]
    bot = dz.telegram.Bot(telegram_token)
    chat_id = os.environ["CHAT_ID"]

    for channel in channels:
        title, video_id, published_time, view_counts = get_newest_video(channel)
        video_url = get_video_url(video_id)
        logger.info(f"Newest video from @{channel}: {title}")

        # Check against database whether video is new
        if title == latest_videos.loc[channel, "title"]:
            logger.info(f"No new videos from @{channel}.")
        else:
            logger.info(f"New video from @{channel}!")
            latest_videos.loc[channel, "title"] = title
            # TODO: Troubleshoot error when writing to csv for >1 channel at a time
            latest_videos.to_csv(file)

            logger.info(f"Updated newest video database.")
            video_url = get_video_url(video_id)
            # Send message
            msg = re.escape(f"[YouTube - {channel}] {title}")
            msg = msg + \
              f" \\({published_time}, {view_counts}\\) \\- [link]({video_url})"
            bot.send_message(chat_id, msg, parse_mode="MarkdownV2")
            # Get captions for new video
            captions = get_captions(video_id)
            # Save captions
            ofile = f"data/captions/{channel}-{video_id}.txt"
            with open(ofile, "w") as file:
                file.write(captions)
            logger.info(f"Saved captions to {ofile}.")
            # Summarise captions and send message
            summary = summarise(captions, "mistral-nemo", 16000)
            bot.send_message(
                chat_id, re.escape(summary), parse_mode="MarkdownV2"
            )
