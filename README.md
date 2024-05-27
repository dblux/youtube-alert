# Youtube Alert

Python script that sends a Telegram message to a specified chat when a new video is uploaded to a YouTube channel. Automatically downloads english captions and summarises it using ollama tinyllama.

## Usage

``` bash
# Insert your own ID and token
export CHAT_ID=""
export TELEGRAM_TOKEN=""

python main.py
```

## Requirements

[dipzy](https://github.com/uuaxe/dipzy) library

## TODO

- [ ] Add feature to summarise captions using the ollama API
- [ ] Fix ValueError: I/O operation on closed file when updating the latest videos of two channels
