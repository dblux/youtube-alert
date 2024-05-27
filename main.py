#!/usr/bin/env python

from bs4 import BeautifulSoup
import html
import logging
import os
import re
import requests
import pandas as pd
import dipzy as dz

logging.basicConfig(
  format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
  level=logging.INFO
)
logger = logging.getLogger(__name__)


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
