# Ish Booty Detector

A website that monitors configured EUNE Riot IDs and displays:

- **ISH BOOTY DETECTED** when at least one account is in a detectable match.
- **ISH BOOTY IS OFFLINE** when none of the accounts is in a detectable match.

## What you need

1. A Riot development API key from <https://developer.riotgames.com/>.
2. A GitHub account and Render account.

Never commit the Riot API key to this repository.

## Test locally (optional)

Install Python 3.11 or newer, then:

```bash
python -m pip install -r requirements.txt
```

PowerShell:

```powershell
$env:RIOT_API_KEY="RGAPI-your-key"
$env:MONITORED_RIOT_IDS="Phvoundves#EUNE;Joshua Graham#DND"
python app.py
```

Stop it with `Ctrl+C`.

## Deploy to Render

1. Create a new private GitHub repository.
2. Upload every file in this project, including `render.yaml`.
3. In Render, select **New → Blueprint**.
4. Connect the GitHub repository.
5. Render will detect the background worker from `render.yaml`.
6. When prompted, enter:
   - `RIOT_API_KEY`
   - `MONITORED_RIOT_IDS`
7. Deploy the Blueprint.
8. Open the service's **Logs** page. You should see both Riot IDs resolved.
9. Open the service's `onrender.com` URL to see the live detector webpage.

The configured `starter` web service is always on. The webpage displays
**ISH BOOTY DETECTED** whenever either monitored player is in a detectable
match and **ISH BOOTY IS OFFLINE** when neither player is in a detectable
match. A free Render web service is less reliable because it sleeps without
inbound traffic.

## Public and private information

The entire repository can be public. It contains only generic application
code. Put these values only in **Render → Environment**:

```text
RIOT_API_KEY=RGAPI-your-key
MONITORED_RIOT_IDS=Phvoundves#EUNE;Joshua Graham#DND
```

Render keeps these values outside the public GitHub repository. A second
private repository is unnecessary. The public webpage and its status endpoint
do not reveal the monitored Riot IDs.

## Updating an expired Riot development key

Riot development keys expire. Generate a replacement, then open:

**Render → lol-match-detector → Environment → RIOT_API_KEY**

Replace the value and save. Render will restart the worker.

## How duplicate prevention works

The worker remembers the live game ID for each player. It sends an alert only
when a new game ID appears and resets that player after the match ends. A Render
restart during an active match can cause one repeated alert because the worker's
memory resets.

## Troubleshooting

- `Riot API key is invalid or expired`: replace `RIOT_API_KEY` in Render.
- `Riot ID not found`: verify spelling, spaces, capitalization, and tag.
- `429`: Riot is rate-limiting requests; the detector automatically waits and retries.
