# Ask Troy treeWISE

Ask Troy is a small local web application that answers questions about Colorado tree care. It uses an Ollama model running on the same machine as the app and can include a tree photo with a question.

The assistant is an AI, not Troy or a certified arborist. It provides general information, does not diagnose trees or assess their safety remotely, and cannot submit service requests or book appointments.

## Features

- Chat about tree identification, pests, diseases, watering, soil, pruning, planting, and preservation.
- Optionally attach a JPG, PNG, or WebP tree photo (up to 5 MB).
- Keep a short conversation history in the browser while the page is open.
- Show an Ollama/model health check through the API.
- Add an extra safety notice for messages that mention certain urgent tree hazards.

## Requirements

- Node.js 18 or newer and npm.
- [Ollama](https://ollama.com/) installed and running on the same machine.
- An Ollama model that supports image input for photo questions. The default is `gemma3:4b`.

The server connects to Ollama at `http://127.0.0.1:11434`. That address is currently fixed in `server.mjs`.

## Run locally

1. Install the Node dependencies:

   ```sh
   npm install
   ```

2. Make sure Ollama is running, then download the default model:

   ```sh
   ollama pull gemma3:4b
   ```

   If Ollama is not already running as a service, start it in a separate terminal:

   ```sh
   ollama serve
   ```

3. Start Ask Troy:

   ```sh
   npm start
   ```

4. Open [http://127.0.0.1:3000](http://127.0.0.1:3000) in a browser.

The server listens on `127.0.0.1` by default, so it is only accessible from the local machine. Set `PORT` to change the port:

```sh
PORT=3001 npm start
```

## Configuration

The app loads `.env` using `dotenv`. The only application setting currently read from the environment is:

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `3000` | Local web server port. |
| `OLLAMA_MODEL` | `gemma3:4b` | Model name to use for chat and report from the health endpoint. Pull the model with `ollama pull <model-name>` before selecting it. |

For example, to use another locally installed model, create or update `.env`:

```dotenv
OLLAMA_MODEL=gemma3:4b
PORT=3000
```

`OLLAMA_URL` is currently hard-coded to `http://127.0.0.1:11434`; it is not an environment variable.

## API

### `GET /api/health`

Checks whether the local Ollama server responds and whether the configured model is installed.

- `200 OK`: Ollama is online. The JSON includes `ollama`, `model`, `installed`, and `local`.
- `503 Service Unavailable`: Ollama could not be reached. The JSON includes `ollama`, `model`, and `installed`.
- If Ollama is online but the selected model is missing, the endpoint still returns `200` with `"installed": false`.

Example:

```sh
curl http://127.0.0.1:3000/api/health
```

### `POST /api/chat`

Sends a user message, optional conversation history, and optional image to the local Ollama model.

Request body:

```json
{
  "message": "Why are the leaves on my tree turning brown?",
  "history": [],
  "image": null
}
```

Fields:

- `message` (required): non-empty string, up to 2,000 characters.
- `history` (optional): array of `{ "role": "user" | "assistant", "content": "..." }` messages; at most 20 entries are accepted. The server uses up to the last 12 valid entries.
- `image` (optional): a `data:image/jpeg;base64,...`, `data:image/png;base64,...`, or `data:image/webp;base64,...` data URL. The browser limits image files to 5 MB.

Successful responses include `answer`, `model`, `local`, `submitted`, and `booked`. `submitted` and `booked` are always `false`; this prototype does not contact the company or schedule appointments. Invalid requests return `400`; Ollama or model failures return `503`.

Example:

```sh
curl -X POST http://127.0.0.1:3000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How often should I water a newly planted tree?"}'
```

## Privacy and safety

- Chat prompts and attached images are sent by the app's server to Ollama at `127.0.0.1`; the app does not call a hosted AI API.
- The browser keeps conversation history in page memory. It is not saved by the app between page loads.
- Do not use this prototype to submit sensitive personal information.
- AI answers are general guidance, not an on-site inspection, diagnosis, formal tree-risk assessment, or guarantee of treatment results.
- Keep people away from potentially unstable trees and branches. Do not attempt hazardous cutting or climbing. Stay clear of electrical hazards and contact the utility; contact emergency services if people are in immediate danger.
- For professional help, call American Tree Colorado at **303-456-6898** or visit [the contact page](https://americantreecolorado.com/contact). The app cannot verify service availability, prices, or appointments.

This server binds to localhost and has no authentication or production deployment hardening. Do not expose it directly to the public internet.

## Troubleshooting

**The app says Ollama is offline**

- Confirm Ollama is running.
- Check the local Ollama endpoint: `curl http://127.0.0.1:11434/api/tags`.
- If needed, start Ollama with `ollama serve`.

**The selected model is not installed**

- Check installed models with `ollama list`.
- Pull the configured model, for example: `ollama pull gemma3:4b`.
- If using photos, choose a vision-capable model supported by your Ollama installation.

**The model responds to text but not photos**

- Confirm the selected model supports image input.
- Use a JPG, PNG, or WebP file no larger than 5 MB.

## Project structure

```text
.
├── public/
│   └── index.html   # Browser chat interface
├── server.mjs       # Express server and Ollama API integration
├── package.json
└── README.md
```
