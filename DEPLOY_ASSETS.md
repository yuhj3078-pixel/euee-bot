Deployment notes — include local notes/audio assets and verify progress aggregation

1. Include local assets in image

- `.dockerignore` was updated to include `notes/` and `audio_lessons/` so local PDFs and MP3s are packaged into the container image. If you prefer to host assets in Supabase Storage, upload files there and populate the `notes` / `audio_lessons` tables with `file_url` entries instead.

2. Environment variables (required)

- `SUPABASE_URL` and `SUPABASE_KEY` (use the Service Role key for server writes when RLS is enabled)
- `ELEVENLABS_API_KEY` (if you use ElevenLabs TTS)
- `PREFER_ELEVENLABS_FOR_AUDIO=true` to prefer ElevenLabs over local TTS
- `BOT_TOKEN`, `WEBHOOK_URL`, `WEBHOOK_SECRET`, `ADMIN_TOKEN`, etc.

3. Row-Level Security (RLS)

- If RLS is enabled in Supabase, your server must use the Service Role key to perform writes (updates/inserts). Confirm `SUPABASE_KEY` used by the deployed app is the service role key, not the anon/public key.

4. SQL snippets to populate `notes` / `audio_lessons` tables (run in Supabase SQL editor):

-- Add a local notes entry (replace file_url with your hosted URL if needed)
INSERT INTO notes (subject, title, content, file_url)
VALUES ('math', 'Maths PDF', '', 'https://example.com/Maths.pdf')
ON CONFLICT (subject) DO UPDATE SET title = EXCLUDED.title, file_url = EXCLUDED.file_url;

-- Add an audio lesson entry
INSERT INTO audio_lessons (subject, title, file_url, file_size_bytes, duration_seconds)
VALUES ('math', 'Math lesson', 'https://example.com/math.mp3', 6200000, 360)
ON CONFLICT (subject) DO UPDATE SET title = EXCLUDED.title, file_url = EXCLUDED.file_url;

5. Verifying Progress aggregation

- Reproduce an answer flow in the bot for a test user and then check the `users` row:

SELECT correct_total, wrong_total, subject_correct, subject_wrong, study_minutes_total FROM users WHERE telegram_id = <TEST_ID>;

- If values are not updating, check server logs for `Updated user user:**` INFO lines (the app now logs keys updated). Also check for logger.exception traces which include masked user refs.

6. Security notes

- Never commit `.env` or real API keys. Use your platform's secrets management (Railway/Heroku/Environment variables).
- The app masks telegram IDs in logs using `safe_user_ref`. Admin notifications still receive masked user refs to avoid leaking IDs.

7. Restart/deploy

- After setting secrets and including assets, redeploy and restart your app so the changes take effect.

8. Optional: If you prefer not to include large media in the image, upload audio PDF/MP3 files to Supabase Storage and populate `file_url` fields in the DB.

If you want, I can prepare a small script to scan `notes/` and `audio_lessons/` and bulk-upload any files to Supabase Storage and insert the corresponding DB rows automatically.

9. Bulk sync script

- Run the current folders into Supabase with:

```powershell
python scripts/sync_assets_to_supabase.py --all
```

- Use `--dry-run` first if you want to preview the actions without uploading anything.
