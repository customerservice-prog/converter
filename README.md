# ClipConvert — MP3 / MP4 conversion

A complete original-design website modeled on the *workflow* of YTMP3: paste a YouTube link, choose MP3 or MP4, convert, and download. The project includes a real Python conversion backend, responsive frontend, browser extension source, bookmarklets, FAQ, thumbnail downloader, temporary job storage and basic abuse controls.

**Independent app.** Not affiliated with ytmp3.gl, YouTube, or Google.

## Features implemented

- YouTube video, Shorts, share-link, embed and finished-livestream URL support.
- **Best available (Auto) is the default** for both types: highest available video resolution and best source audio encoded to 320 kbps MP3. Users can still set manual limits (MP3: 128/192/320 kbps, MP4: 360/720/1080/1440/2160p).
- Up to 240 minutes for MP3, 30 minutes for MP4.
- yt-dlp + yt-dlp-ejs + Node 22 challenge runtime + FFmpeg for actual conversion (no fake download button).
- Server-side background jobs, live progress polling, video title/thumbnail, download links, error handling, 1-hour file lifetime and janitor cleanup every five minutes.
- Rate limits, concurrent job caps, arbitrary-URL rejection, canonical YouTube URL validation, random download IDs, non-root Docker.
- Responsive dark design, no login, paste button, keyboard navigation, basic accessibility.
- /faq, /add-on, /bookmarklet, /thumbnail, /contact, /privacy, /copyright, /terms.
- Browser extension source (Chromium and Firefox temporary add-on); deployment-domain setting in its popup.
- Optional SMTP contact form (requires configuring environment variables).

## Run locally

Requires Python 3.12+, FFmpeg and Node 22+ in PATH.

    python -m venv .venv
    source .venv/bin/activate  # on Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app:app --reload

Open http://localhost:8000. Run tests:

    python -m unittest discover -s tests -v

If local Python lacks the Node runtime, YouTube conversions may fail. Docker bundles Node 22 and FFmpeg automatically.

## Deploy (Railway or any Docker host)

1. Create a Railway service from **customerservice-prog/converter** or deploy the Dockerfile on your Docker-capable host.
2. Select the Dockerfile build. Bind the application's supplied PORT automatically.
3. Set the service health check to **/api/health**. Ensure at least 1 GB available RAM, adequate CPU, disk, and bandwidth for media processing.
4. Generate a public HTTPS domain and test a *video you own or have permission to download* end to end.
5. Configure your operating contact details and SMTP environment before public release.

Local Docker smoke test:

    docker build -t clipconvert .
    docker run --rm -p 8080:8080 clipconvert

Open http://localhost:8080.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| PORT | 8080 | Server listening port |
| MAX_ACTIVE_JOBS | 2 | Concurrent conversions |
| DAILY_LIMIT | 20 | Requests per IP per rolling day |
| MAX_FILE_MB | 512 | Maximum output size in MB |
| MEDIA_DIR | /tmp/converter-media | Temporary file directory |
| FILE_TTL_SECONDS | 3600 | File retention in seconds |
| CONTACT_EMAIL | unset | Form destination |
| SMTP_HOST | unset | SMTP server; enables contact form |
| SMTP_PORT | 587 | SMTP port (STARTTLS) |
| SMTP_USER | unset | SMTP login |
| SMTP_PASSWORD | unset | SMTP password |
| SMTP_FROM | CONTACT_EMAIL | Verified sender |

No keys or third-party conversion API subscriptions are needed. **Self-hosting still consumes server CPU, storage and bandwidth and may cost money.**

## Browser extension

Load the /extension directory as an unpacked developer extension in Chrome/Edge/Opera, or as a temporary Firefox extension. Enter the URL of your deployed site in the popup, then open a YouTube video and choose MP3 or MP4. Store publication requires separate approvals. Bookmarklets are generated for the deployed host at /bookmarklet.

## Important production constraints

- The build code is complete, but this repository is **not automatically a live hosted website**. GitHub Actions runs syntax/unit checks, *not* a real YouTube end-to-end download.
- YouTube changes its extraction methods and may reject cloud datacenter addresses or restrict particular media. Not every video is guaranteed to work. The service does **not** bypass DRM, authentication, private-content restrictions or geographic access controls.
- MP4 above 360p depends on source availability and compatible streams.
- Jobs, quotas and media files are maintained on a single local instance. Scaling beyond one worker/instance requires Redis or another shared job queue, durable object storage and distributed rate limits. For public high traffic also add CDN, monitoring, resource caps, abuse handling and operational complaint workflows.
- No ads or analytics are included in the application, but the Google Fonts request and the hosting platform may generate third-party access logs.
- Users must have rights to download the submitted media and comply with laws and applicable platform terms. The legal pages are preliminary and must be customized by the operator before launch.

## Testing

Unit tests cover URL allowlisting and supported formats; GitHub Actions runs them on push. Check /api/health to verify FFmpeg is on the server, and check the actual browser conversion journey after deployment. Avoid claiming real YouTube conversion is verified until tested on the deployed server.


## November 8, 2026: verified Railway YouTube-link fix

**Live URL:** https://clipconvert-web-production.up.railway.app

The initial version failed for YouTube video `NY6acnscmwo` because YouTube issued a bot-verification challenge to the Railway datacenter's IPv4 egress. The production service now successfully retrieves and converts this same link when configured for outbound IPv6.

**Required Railway settings for this deployment:**

1. Enable **Outbound IPv6** for the ClipConvert service (Railway Settings → Networking).
2. Set the service variable `PREFER_IPV6=1`. The Python backend binds yt-dlp's outgoing requests to IPv6 when this flag is enabled.
3. Keep `yt-dlp[default]` current, with Node 22 and FFmpeg included in the provided Dockerfile.
4. Retain the deployed health check at `/api/health` and single-instance media storage until shared job storage has been implemented.

**Verified result:** GitHub Actions [Live production checks](https://github.com/customerservice-prog/converter/actions/runs/42507970967) completed both MP4 360p and MP3 192kbps conversions of `NY6acnscmwo`, polled for ready jobs, requested actual downloadable results from Railway, and validated the format responses and media bytes. File uploads were separately verified. The production smoke test now **fails** if either direct-link conversion or download fails, so the result cannot be hidden behind a passing homepage health check.

**Important limitation:** YouTube can still change its access rules, restrict individual videos, or restrict the current IPv6 address. This test is proof that the specified formats worked at the time of testing, **not a guarantee that every YouTube URL will work indefinitely**. No personal Google credentials or cookie scraping is used. Only convert content you have permission to download. A permitted media-file upload option remains available.

**Other settings:** `MAX_UPLOAD_MB` defaults to 100 MB. Uploads are checked with ffprobe and converted with FFmpeg, and temporary files are cleaned after their retention period.

## Best-quality default

The quality selector defaults to `0` (**Best available / Auto**) in the UI, YouTube API and file upload API. For MP4 links, yt-dlp selects the best video and audio streams without a resolution cap and merges to MP4. This may include 4K or higher if available. For MP3, the best available source audio is encoded to 320 kbps; that output bitrate **cannot restore information missing from a lower-quality source**. For user-uploaded video, Auto preserves the original dimensions and remuxes compatible H.264/HEVC + AAC streams without recompression, or uses a high-quality encode where necessary. The completed-job status reports actual resolution or MP3 bitrate. High-quality media takes more time, bandwidth, and temporary storage; limits still apply.


## Multi-link batch conversion

Select **Multiple links** on the converter homepage. Paste **2–10 distinct YouTube URLs, one per line**, choose MP3 or MP4, and keep **Best available (Auto)** for full source quality. Up to two videos can be processed concurrently, bounded by the service's global conversion limit. The live batch screen shows every item's status, title, progress, quality, errors, and individual folder download link. When all work completes, **Download all videos** produces one ZIP with a separate folder for every successful video, plus an overall Batch Results.txt. A failed link doesn't discard successfully processed media.

Batches share the normal 20-per-network-address rolling daily conversion quota. Conversion output stays temporarily on the server (default one hour after the batch finishes), and the batch ZIP is built only when requested with ZIP_STORED—no extra media recompression.

**Limits:** this is currently a single Railway instance with in-memory jobs and temporary local files. A server restart or deployment during active conversions clears those jobs; for durable long-running batches, add a persistent queue and shared object storage. A website cannot directly create folders on the user's desktop; the downloaded ZIP contains the folders when extracted. This is not YouTube playlist downloading.


## November 8, 2026 — MP4 audio compatibility fix

**Problem:** Some MP4 files downloaded with best-available video resolution could appear silent in certain players, because a successful video-only download and MP4 file header check did not guarantee a compatible audio track.

**Fix:**
- The MP4 yt-dlp selector is now \`bestvideo+bestaudio/best\` so it explicitly chooses separate video and audio streams when available.
- The server inspects the completed MP4 with ffprobe. Files missing an audio track will fail with an explicit error rather than silently downloading.
- Incompatible audio codecs such as Opus are converted to **AAC stereo at 256 kbps**, while the video stream is copied **without video re-encoding**. Existing compatible AAC mono/stereo audio is left untouched to keep conversion fast.
- FFmpeg decodes a portion of the output audio to catch corrupted audio tracks before the Download button appears.
- Conversion results expose \`audio_codec\` and \`audio_channels\`, and show **AAC audio verified** in the interface.
- The test suite synthesizes an MP4 with Opus audio, repairs it, verifies the video stream is unchanged, decodes non-silent audio samples, and tests that AAC inputs are not re-encoded. The live production workflow checks that MP4 downloads actually report a verified AAC track.

**Limitations:** Audio cannot be created from a source that has no audio track. A media player's hardware codec support for 4K video is a separate issue from the audio stream. Files downloaded before this change must be converted again; the server cannot retroactively modify an existing download.
