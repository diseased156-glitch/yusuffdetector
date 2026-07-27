import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOG = logging.getLogger("lol-match-detector")

RIOT_API_KEY = os.environ["RIOT_API_KEY"]
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
SITE_URL = os.getenv(
    "SITE_URL",
    "https://yusuffdetector.onrender.com/",
).strip()
PLATFORM = os.getenv("RIOT_PLATFORM", "eun1").lower()
REGION = os.getenv("RIOT_REGION", "europe").lower()
CHECK_INTERVAL = max(20, int(os.getenv("CHECK_INTERVAL", "30")))


@dataclass
class Player:
    game_name: str
    tag_line: str
    puuid: Optional[str] = None
    last_game_id: Optional[str] = None

    @property
    def riot_id(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


def load_players() -> list[Player]:
    raw_ids = os.environ["MONITORED_RIOT_IDS"]
    players = []
    for riot_id in raw_ids.split(";"):
        riot_id = riot_id.strip()
        if not riot_id:
            continue
        if "#" not in riot_id:
            raise RuntimeError(
                f"Invalid Riot ID '{riot_id}'. Expected GameName#Tag."
            )
        game_name, tag_line = riot_id.rsplit("#", 1)
        players.append(Player(game_name.strip(), tag_line.strip()))
    if not players:
        raise RuntimeError("MONITORED_RIOT_IDS contains no Riot IDs.")
    return players


PLAYERS = load_players()

STATUS_LOCK = threading.Lock()
PLAYER_STATUS = {
    player.riot_id: {
        "in_game": False,
        "game_id": None,
        "map": None,
        "mode": None,
        "last_checked": None,
        "error": None,
    }
    for player in PLAYERS
}


def update_status(player: Player, **changes) -> None:
    with STATUS_LOCK:
        status = PLAYER_STATUS.setdefault(
            player.riot_id,
            {
                "in_game": False,
                "game_id": None,
                "map": None,
                "mode": None,
                "last_checked": None,
                "error": None,
            },
        )
        status.update(changes)


def riot_get(url: str) -> requests.Response:
    response = requests.get(
        url,
        headers={"X-Riot-Token": RIOT_API_KEY},
        timeout=15,
    )
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "10"))
        LOG.warning("Riot rate limit reached; waiting %s seconds.", retry_after)
        time.sleep(retry_after)
        response = requests.get(
            url,
            headers={"X-Riot-Token": RIOT_API_KEY},
            timeout=15,
        )
    return response


def resolve_puuid(player: Player) -> None:
    name = quote(player.game_name, safe="")
    tag = quote(player.tag_line, safe="")
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    )
    response = riot_get(url)
    if response.status_code == 401 or response.status_code == 403:
        raise RuntimeError("Riot API key is invalid or expired.")
    if response.status_code == 404:
        raise RuntimeError(f"Riot ID not found: {player.riot_id}")
    response.raise_for_status()
    player.puuid = response.json()["puuid"]
    LOG.info("Resolved %s.", player.riot_id)


def get_active_game(player: Player) -> Optional[dict]:
    if not player.puuid:
        resolve_puuid(player)
    puuid = quote(player.puuid, safe="")
    url = (
        f"https://{PLATFORM}.api.riotgames.com"
        f"/lol/spectator/v5/active-games/by-summoner/{puuid}"
    )
    response = riot_get(url)
    if response.status_code == 404:
        return None
    if response.status_code == 401 or response.status_code == 403:
        raise RuntimeError("Riot API key is invalid or expired.")
    response.raise_for_status()
    return response.json()


def map_name(map_id: int) -> str:
    return {
        11: "Summoner's Rift",
        12: "Howling Abyss",
        21: "Nexus Blitz",
        22: "Teamfight Tactics",
        30: "Arena",
        33: "Swarm",
    }.get(map_id, f"Map {map_id}")


def send_discord_notification(player: Player, game: dict) -> None:
    if not DISCORD_WEBHOOK_URL:
        LOG.info("DISCORD_WEBHOOK_URL is not configured; skipping notification.")
        return

    current_map = map_name(game.get("mapId", 0))
    current_mode = game.get("gameMode", "Unknown mode")
    payload = {
        "username": "Ish Booty Detector",
        "embeds": [
            {
                "title": "🚨 ISH BOOTY DETECTED",
                "description": (
                    "Ish Booty has entered a League of Legends map.\n\n"
                    f"**Map:** {current_map}\n"
                    f"**Mode:** {current_mode}\n"
                    f"[Open the live detector]({SITE_URL})"
                ),
                "color": 16719176,
            }
        ],
    }
    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    LOG.info("Sent Discord notification for game %s.", game.get("gameId"))


def check_player(player: Player) -> None:
    game = get_active_game(player)
    if game is None:
        if player.last_game_id is not None:
            LOG.info("%s is no longer in game.", player.riot_id)
        player.last_game_id = None
        update_status(
            player,
            in_game=False,
            game_id=None,
            map=None,
            mode=None,
            last_checked=int(time.time()),
            error=None,
        )
        return

    game_id = str(game["gameId"])
    update_status(
        player,
        in_game=True,
        game_id=game_id,
        map=map_name(game.get("mapId", 0)),
        mode=game.get("gameMode", "Unknown mode"),
        last_checked=int(time.time()),
        error=None,
    )
    if game_id != player.last_game_id:
        LOG.info("%s entered game %s.", player.riot_id, game_id)
        try:
            send_discord_notification(player, game)
        except requests.RequestException as error:
            LOG.warning("Could not send Discord notification: %s", error)
        player.last_game_id = game_id


def public_status() -> dict:
    with STATUS_LOCK:
        statuses = [dict(status) for status in PLAYER_STATUS.values()]
    return {
        "detected": any(status["in_game"] for status in statuses),
        "last_checked": max(
            (status["last_checked"] or 0 for status in statuses),
            default=0,
        ),
    }


def monitor_forever() -> None:
    LOG.info(
        "Monitoring %s on %s every %s seconds.",
        ", ".join(player.riot_id for player in PLAYERS),
        PLATFORM,
        CHECK_INTERVAL,
    )
    while True:
        for player in PLAYERS:
            try:
                check_player(player)
            except RuntimeError as error:
                LOG.error("%s", error)
                update_status(player, error=str(error))
            except requests.RequestException as error:
                LOG.warning("Network/API error for %s: %s", player.riot_id, error)
                update_status(player, error="Riot API unavailable")
            except Exception:
                LOG.exception("Unexpected error while checking %s.", player.riot_id)
                update_status(player, error="Unexpected detector error")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_forever()
