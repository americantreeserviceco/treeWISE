# Ask Troy treeWISE

Ask Troy is a small local web application that answers questions about Colorado tree care. It uses an Ollama model running on the same machine as the app and can include a tree photo with a question.

The assistant is an AI, not Troy or a certified arborist. It provides general information, does not diagnose trees or assess their safety remotely, and cannot submit service requests or book appointments.

## Features

- Chat about tree identification, pests, diseases, watering, soil, pruning, planting, and preservation.
- Optionally attach a JPG, PNG, or WebP tree photo (up to 5 MB).
- Keep a short conversation history in the browser while the page is open.
- Show an Ollama/model health check through the API.
- Add an extra safety notice for messages that mention certain urgent tree hazards.
- Retrieve relevant version-controlled tree-care guidance locally and show general reference topics in chat. No network search is performed.

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

Successful responses include `answer`, `model`, `local`, `submitted`, `booked`, and `sources` (curated reference topics). `submitted` and `booked` are always `false`; this prototype does not contact the company or schedule appointments. Invalid requests return `400`; Ollama or model failures return `503`.

Example:

```sh
curl -X POST http://127.0.0.1:3000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How often should I water a newly planted tree?"}'
```

## Knowledge retrieval

The app keeps a small, editable reference library in `knowledge.mjs`. Queries use deterministic keyword matching, not embeddings, so they run without a second model and do not call external search services. Relevant notes are inserted into the model prompt and returned as `sources`; those links are general reference sites, not citations to individually verified articles. The library is starter content and needs arborist and editorial review before public release. When no entry matches, the assistant uses its general system instructions without fabricated references.

Run `npm test` to check the retrieval module. A future milestone can add embedding-based semantic search, a document ingestion pipeline, and reviewed article-level citations.

## Local inquiry intake (development only)

The inquiry feature is **disabled by default**. It does not email the office, notify staff, book appointments, or upload photos. It is deliberately not a production customer-contact integration.

To enable it for local tests, choose a private location **outside the repository and public web root**:

```sh
install -d -m 700 "$HOME/.local/share/treewise-inquiries"
ENABLE_INQUIRY_INTAKE=true \
INQUIRY_QUEUE_FILE="$HOME/.local/share/treewise-inquiries/requests.jsonl" \
npm start
```

The directory must already have private permissions (0700), and the queue file is created with permissions 0600. An existing queue file with broader permissions, or a symlinked queue file, is rejected. The service binds to 127.0.0.1. Do not enable this feature on a publicly reachable server.

### API

- `GET /api/inquiry/config`: returns whether local intake is enabled; reports that photo submission is unsupported.
- `POST /api/inquiries`: validates name, email or phone, description, priority and explicit consent. When enabled, returns `201` with a UUID reference, `status: "saved-locally"`, and `deliveredToOffice: false`. Disabled intake returns `503`.
- Each accepted inquiry is saved as one JSON object per line with a pending status. Do not commit, email, or expose this file through the web server.
- The endpoint includes a small in-memory request limiter and a hidden spam-trap field. Neither is adequate as the sole protection for public deployment.

**Staff review:** No authenticated office dashboard or delivery adapter exists yet. Authorized local operators must review the private queue by an approved secure process. Establish retention, deletion, access controls, encryption/backup policy, and a privacy notice before collecting real customer information. For now, use synthetic test data only.

**Photo handling:** A photo may still be attached to a chat question for local Ollama inference, but the inquiry form never transmits that image or the conversation history.

`npm test` runs the built-in Node.js regression suite. For an end-to-end smoke test, start the local server with intake enabled, then submit a synthetic inquiry to `/api/inquiries` and verify its UUID and private queue record. Do not mistake a local-save receipt for delivery to the office.

## Sprint 4: Private staff review prototype

A local staff dashboard is available at `http://127.0.0.1:3000/staff.html` when the application is running. The page itself contains no customer records; its API requires an access token. This is an **operator prototype**, not a production-ready staff identity system.

Set a long random access token and the intake environment settings before starting:

```sh
install -d -m 700 "$HOME/.local/share/treewise-inquiries"
export ENABLE_INQUIRY_INTAKE=true
export ENABLE_STAFF_REVIEW=true
export INQUIRY_QUEUE_FILE="$HOME/.local/share/treewise-inquiries/requests.jsonl"
export STAFF_REVIEW_TOKEN="$(openssl rand -hex 32)"
printf 'Temporary staff token: %s\n' "$STAFF_REVIEW_TOKEN"
npm start
```

The token above is printed solely for interactive local testing; **do not put it in logs, paste it into tickets, commit it, or use the sample workflow on a public host**. Use a protected secrets store and per-user authentication before production rollout. The access token is entered into the dashboard manually and held only in tab memory.

Staff endpoints:
- `GET /api/staff/inquiries` lists local queue records and their latest workflow state.
- `PATCH /api/staff/inquiries/:id` accepts JSON `{"status":"reviewing","note":"Review started"}`. Allowed states: `pending`, `reviewing`, `contacted`, `resolved`, `closed`.
- Every staff request must send `Authorization: Bearer <token>`. Failed authentication returns 401; the server does not return customer records.
- Updates append to `requests.jsonl.events` and preserve the originally submitted record.

**Known limitations:** Single shared token (no individual accountability), no login session management, no secure remote access, no multi-process locking, no retention/deletion workflow, no queue pagination, no electronic office delivery, and no production audit controls. The queue and event files contain personal information and must not be copied into public builds or backups accessible to unauthorized users. Run only on localhost with synthetic data.

Run `npm test`; the GitHub Actions workflow also runs syntax checks and Node tests on pull requests.

## Sprint 5: PostgreSQL and individual staff authentication (experimental)

The optional `TREEWISE_STORAGE=postgres` mode stores incoming inquiries in PostgreSQL, authenticates individual staff users with salted scrypt password hashes, and stores only SHA-256 digests of random bearer session tokens. Staff sessions last eight hours by default. Status changes are written to an inquiry audit table with a staff ID within the same database transaction as the status update.

**This branch is not ready to merge or deploy** until the PostgreSQL driver installation, committed lockfile, database migration and live integration tests are complete. The existing JSONL/shared-token development workflow remains the default. PostgreSQL mode is enabled only when explicitly configured.

### Provisioning (isolated development database only)

1. Create a separate PostgreSQL role and database with limited privileges. Never use the PostgreSQL superuser as the app identity.
2. Apply `db/001_init.sql` using an authorized migration role, e.g. `psql "$MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/001_init.sql`.
3. On an environment with npm registry access, run `npm install pg@8.23.1 --save` and **commit the regenerated `package.json` and `package-lock.json` before merging**. The library is not vendored in this branch; the runtime imports it dynamically only when PostgreSQL mode is enabled.
4. Set `TREEWISE_STORAGE=postgres`, `DATABASE_URL`, and `ENABLE_INQUIRY_INTAKE=true` in a private environment. Use a separate credential to create staff users.
5. Create a staff user through `node scripts/create-staff.mjs` with `TREEWISE_STAFF_USERNAME`, `TREEWISE_STAFF_DISPLAY_NAME`, and `TREEWISE_STAFF_PASSWORD` supplied privately. Prefer an interactive secrets manager over shell history, CLI arguments, or storing credentials in a committed file.
6. Open `/staff.html`, sign in, and test listing, state updates, log out and session expiry with synthetic inquiries. Do not use actual customer details during development.

API additions:
- `POST /api/staff/login` accepts username and password, returns a bearer token and expiry in PostgreSQL mode.
- `POST /api/staff/logout` revokes the current server-side session.
- Existing `GET /api/staff/inquiries` and `PATCH /api/staff/inquiries/:id` use authenticated database sessions when PostgreSQL mode is enabled.
- Existing `POST /api/inquiries` writes to PostgreSQL instead of the JSONL queue in that mode.

### Production blockers

Before using real customer data: complete live PostgreSQL integration tests, migrations and rollback strategy, role-specific least privilege, network/TLS policy, credential rotation, user provisioning and reset/revocation, session management, abuse controls, authorization by role, retention/deletion and backups, CSRF/origin defense for any future cookie-based auth, and encrypted transport. Neither the existing localhost server nor the current dashboard should be exposed directly to the internet.

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
├── knowledge.mjs    # Local curated retrieval library
├── inquiries.mjs    # Validated, disabled-by-default local inquiry queue
├── staff.mjs        # Development shared-token staff workflow
├── auth.mjs         # Password and session token primitives
├── postgres.mjs     # Opt-in parameterized PostgreSQL adapter
├── db/001_init.sql  # Database schema migration
├── scripts/create-staff.mjs # Development staff bootstrap
├── public/staff.html # Local staff review UI
├── test/staff.test.mjs
├── test/inquiries.test.mjs
├── test/knowledge.test.mjs
├── package.json
└── README.md
```
