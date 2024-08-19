# Youtube Alert

Python script that sends a Telegram message to a specified chat when a new video is uploaded to a YouTube channel. Automatically downloads english captions and summarises it using any Ollama served LLMs.

## Usage

``` bash
# Insert your own ID and token
export CHAT_ID=""
export TELEGRAM_TOKEN=""

python main.py
```

## Requirements

- [dipzy](https://github.com/uuaxe/dipzy) python library
- [Ollama](https://github.com/ollama/ollama-python) python library

## TODO

- [x] Add feature to summarise captions using ollama served LLMs 
- [ ] Fix ValueError: I/O operation on closed file when updating the latest videos of two channels
