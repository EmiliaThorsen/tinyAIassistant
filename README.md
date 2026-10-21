# tinyAIassistant
A natural language voice/chat assistant for Home Assistant that runs on a Raspberry Pi, without a full LLM.

## Why
There are two common ways to do a chat or voice assistant for Home Assistant, and both have problems.

**Pattern matching.** This is the default: a big generated list of sentence templates that commands get matched against. It falls apart with natural language. "Turn off bedroom light" might work, but say "lights" instead of "light", or "shut off"/"deactivate" instead of the exact expected words, and it doesn't. That is a real annoyance for me. I'm bad at memorizing exact phrases, I'm dyslexic, and I'm Swedish, so I want to be able to talk to it in Swedish too.

**A full LLM.** Feeding requests into an LLM with tool calling or MCP is very powerful, and in theory the perfect solution. In practice LLMs are heavy. You either run a beefy local inference server, or send your home's details to a paid API for every request. I don't want to pay per request or keep my PC's GPU busy running a glorified light switch. And on the Raspberry Pi 4 that runs my HA, llama.cpp on the CPU could only fit a 2-3B model and would be painfully slow.

## How
There is a class of small models built specifically to take natural language and output decisions. They are sometimes called "system one" models. You give one the text plus a set of questions, like a form to fill in (pick one of these options, give a score, true/false), and it answers each with a confidence. That fits tool calling and commands like "set all lamps to 50" well. Open weight versions of these are under half a billion parameters and answer in a single forward pass, which makes them cheap enough to run on a Pi. This project uses [laya](https://github.com/NandhaKishorM/laya) (`convaiinnovations/laya` on Hugging Face), specifically its multilingual checkpoint so Swedish and English both work with one model.

To let the assistant do a lot of things without dumping every tool's details into the model's context, it works like a text based choose-your-own-adventure game:

1. The **main menu** asks the model which plugin should handle the request, based on each plugin's short description (or "none").
2. The chosen **plugin** then asks its own follow-up questions about the specifics, e.g. which light and what to do with it.

Each step keeps the options small and scoped, which reduces mistakes, and the model never sees details of tools that aren't relevant.

Plugins are separate files in `plugins/`. Dropping a new file in that folder adds a new ability, so other people could write their own. A plugin only needs a name and a description for the main menu, plus a `run` method that does whatever it wants. It can be as simple as telling the time or as involved as a multi-step flow.

## Setup
```sh
python -m venv .venv
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install laya wyoming
cp config.example.toml config.toml
```
Then edit `config.toml`:
- `[homeassistant]`: your HA URL and a long-lived access token (HA profile → Security). With no token, actions are only printed (dry run).
- `[lights]`: your light entity ids mapped to descriptive names. `.venv/bin/python -m core.homeassistant` lists the lights HA knows about.
- `[light_levels]`, `[light_colors]`, `[light_temperatures]`: optional, the brightness levels, colors and white temperatures the model picks between.

The example config has notes on what wording works well for the model.

## Running
Type prompts in the terminal, one per line (also works piped):
```sh
.venv/bin/python main.py
```
Or run as a [Wyoming](https://github.com/OHF-Voice/wyoming) server so Home Assistant can use it as a conversation agent:
```sh
.venv/bin/python main.py --uri tcp://0.0.0.0:10500
```
In HA, add the **Wyoming Protocol** integration pointing at that host and port, then create a voice assistant under Settings → Voice assistants that uses `tinyAIassistant` as its conversation agent, with your usual speech-to-text and text-to-speech. Turn off "prefer handling commands locally" if HA shows that option, otherwise HA's own matcher gets each request first.

Other flags: `--config` to use another config file, `--model` to pick a different laya checkpoint, `--min-confidence` for when the main menu gives up, `-q` to hide the debug output. See `--help`.

### Request log
Every request is appended to `logs/requests.jsonl`: the prompt, every question the model was asked with the exact options, its answers and confidences, and what the plugin ended up doing. The point is to start collecting real data right away. A larger LLM can label it and generate more wordings, and the result can be used to fine-tune the model. `--log` changes the path, `--no-log` turns it off.

## Plugins
- **lights**: turns HA lights on/off and sets brightness, color and white temperature. Brightness either comes from a spoken number ("30 percent", "femtio procent") or from one of the configured levels ("dim", "moody", "max"). If the model isn't confident which light you meant, it does nothing rather than guessing.
- **time**: tells the current time.
- **weather**: placeholder, only says which day you asked about.

## Current state
### Done
- laya running on CPU, multilingual checkpoint only
- Main menu + plugin system with auto-discovered plugin files
- Stdin input for testing, and a Wyoming server so HA can use it as a voice/chat assistant
- Lights plugin controlling real lights through the HA REST API
- Request logging for future training data

### Known issues
- The model leans heavily on shared words rather than meaning. A light described as "light in the hallway" caught every request containing "light", and a brightness level named "bright" caught "full brightness". Descriptions need to be written with that in mind.
- It can't turn numbers into values by itself ("five percent" became max), so spoken numbers are parsed with plain text matching for now. I'd rather the model understood them properly, and fine-tuning should help.
- Requests that never mention a light ("daylight in the kitchen", "make it look like a sunset") often don't reach the lights plugin at the main menu. Swedish requests are less reliable than English ones.
- No conversation history, so it can't ask a follow-up question like "which light?".
- Uses about 1.8 GB of RAM, a lot for the Pi. Lower precision weights should help.
- My speech-to-text setup mishears a lot ("lamps" → "lumps") and doesn't handle Swedish at all, so far Swedish has only been tested with typed text.

### Planned
- Fine-tune the model on the logged requests
- Relative changes ("a bit brighter"), groups of lights, rooms
- Make the placeholder plugins real: weather, time in other places, device state, spoken out loud through a local Piper TTS
- Conversation history, so it can ask follow-up questions
- Move it to the Pi

### Maybe later
- Phone notifications of actions taken, possibly with a way to give feedback to generate fine-tuning data
- Calendar information
- Todo list reading and ticking off entries
- Alarms and timers
- Fridge inventory tracking
- Far future: a fine-tuned speech-to-text model, or a model that takes audio directly instead of a transcript
