# Contract: HTTP endpoints

One Cloud Run service, `pantry-bot`, europe-west1. Ingress all; the app authenticates every route itself.

## POST /telegram/webhook

- **Caller**: Telegram, registered with `setWebhook(url, secret_token, max_connections=1,
  allowed_updates=["message","callback_query"])`.
- **Auth**: header `X-Telegram-Bot-Api-Secret-Token` must equal the `TELEGRAM_WEBHOOK_SECRET` secret,
  compared in constant time. Mismatch: `401`, nothing logged beyond the status.
- **Body**: a Telegram `Update`.
- **Allow-list (FR-002)**: if the chat id is not in `TELEGRAM_ALLOWED_CHAT_IDS`, return `200` with no
  reply and no data access beyond the allow-list check.
- **Duplicate**: if `update_id` is already in `pantry_updates`, return `200` and do nothing.
- **Handling**: photo, text and callback query per [bot-commands.md](bot-commands.md). The reply is sent
  with `sendMessage` before the response returns.
- **Response**: always `200 {"ok": true}` once authenticated, also on internal errors (logged with type
  only, owner gets a short Hebrew error reply), so Telegram does not retry a poison update.

## POST /tasks/morning

- **Caller**: Cloud Scheduler job `pantry-morning`, `30 7 * * *`, Asia/Jerusalem.
- **Auth**: `Authorization: Bearer <OIDC id token>`; audience = service URL, email = the
  `pantry-scheduler` service account. Anything else: `401`.
- **Effect**: computes run-out items against `pantry_baseline/current`, sends one message to each
  allow-listed chat, writes the new baseline.
- **Response**: `200 {"sent": n, "run_out": k}`. Idempotent per calendar day: a second call on the same
  Asia/Jerusalem date returns `200 {"sent": 0}`.

## GET /healthz

- **Auth**: none. **Response**: `200 {"ok": true, "model": "<onnx file name>"}`. No data access.

## Outbound calls

| Target | Call | Data sent |
|--------|------|-----------|
| Telegram Bot API | `getFile`, file download, `sendMessage`, `answerCallbackQuery`, `editMessageReplyMarkup` | reply text only |
| Anthropic Messages API | `messages.create`, model `claude-haiku-5-5` | one padded crop, the item key list |
| Firestore, Cloud Storage | client libraries with the run service account | photos to `photos/yyyy/mm/dd/<uuid>.jpg` |
