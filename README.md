# tinyAIassistant
this is my implementation of a home assistant chat assistant. It has some nice advantages over current solutions for HA.

The most common method of doing chat and voice assistant for HA is to use a pattern matching system and a huge generated corpus of potential voice commands. This has one very large issue tho. It doesn't handle natural language well. say "turn off bedroom light" and it might work, but if you happen to pluralize the "light" into "lights" it breaks, if you say "shut off"/"turn down"/"deactivate" etc instead of the exact correct thing it doesn't work. This is a major annoyance to me as i suck at memorizing things and happen to be dyslexic, not to mention Im Swedish so i might want to tell it stuff in Swedish.

The second approach people use is running the thing straight into an LLM. This is immensely powerful and with the assistant API and MCP lets you do nearly anything. Its the theoretical perfect solution. This is somewhat exactly what LLMs are made for. But, there are some issues. For one, LLMs are very hardware intensive, either you need to run a beefy local inference server, or you need to send your personal home details to an API and pay per input. Using apis and paying for things like this sounds ridiculous. And i dont want to occupy my pcs gpu running a glorified light switch. If i tried to run an LLM on llama.cpp cpu inference on my raspberry pi 4b+ (that my HA is on), i would only be able to fit a 2-3b model and it would run at a horrible speed. Its simply not feasible.

## what this project does instead
now we have AI models that are specifically designed to take in natural language and output decisions. Typesafe ai that made the first one call these models "system one models". you can input your prompt as well as values like in a form for it to fill in (and it gives confidence ratings to its inputs). This is basically perfect for tool calling and automation like "set all lamps to 50" and similar requests. And the best part is there are open weight models that do this at less than half a billion parameters, and its a single forwards pass. This makes it incredibly cheap compute wise, and easily fits in half a gb of ram.

To facilitate the model being able to have a large amount of things it can do, while keeping it scoped (to reduce potential errors), while not filling the entire context with tool specifications, is this system structured in a kind of "text based choose your own adventure game", where we effectively make a main menu with sub menus. The model chooses what family of tools to run, then it gets prompted again on the specifics of the tool. For example we might have a package doing home assistant light controls, and one doing calendar readings. Keeping all of it in one big list in the start gets bad, so instead it first chooses what to do, then the specifics, without filling half the context with specifics that add nothing.

## technical specifics
This project is designed to be very expandable. there is a main server implementation that handles the HA assist api, running the decision model, and the main menu. Then from the main menu the model can decide what tool it wants to use, these are all separate files. In the future if this takes off, someone else could write their own tool file, and due to its specification adding it to the tool folder would give the assistant that ability. Plugins of sorts. 

The tools cab be as simple or complex as you wish, all they have to do is give an explanation of what they do to add to the start prompt, and then give the next steps down that "tool adventure". It can be as simple as making a local TTS say the current time and do nothing, to a sophisticated multi-step system for something much more complex. 

## current project state and plans
### done
nothing yet
### planned
get laya working (open model, convaiinnovations/laya on HF)
implement main system with prompt handling and tools
implement the stuff to have HA communicate with it
make a tool that lets it control my lights and see their state
make a simple information giver, things like current weather, time in various places, device state. And have it send it to a local piper model to say it out loud
### maybe later plugins
phone notifications of actions taken, potentially with a feedback giving system to generate fine tune data
calendar information
todo list reading, ticking off entries
setting alarms, timers
fridge inventory tracking
