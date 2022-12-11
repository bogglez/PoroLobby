#!/usr/bin/env python3

import aiohttp
import asyncio
import psutil
import random

async def create_lobby(connection, game_mode, lobby_name, password, spectator_policy):
    if game_mode not in ["PRACTICETOOL", "CLASSIC"]:
        raise ValueError(f'game_mode={game_mode}')

    if spectator_policy not in ["AllAllowed", "NotAllowed"]:
        raise ValueError(f'spectator_policy={spectator_policy}')

    data = {
        "isCustom": True,
        "customGameLobby": {
            "configuration": {
                "gameMode": game_mode,
                "mapId": 11,
                "mutators": {
                    "id": 1
                },
                "spectatorPolicy": spectator_policy,
                "teamSize": 5,
            },
            "lobbyName": lobby_name,
            "lobbyPassword": password
        },
    }
    async with connection.post('/lol-lobby/v2/lobby', json=data) as response:
        if response.status != 200:
            raise RuntimeError("Cannot create lobby.")
        return await response.json()

async def get_available_bots(connection):
    async with connection.get('/lol-lobby/v2/lobby/custom/available-bots') as response:
        if response.status != 200:
            raise RuntimeError("Cannot request available bots.")
        return await response.json()

def get_champion_id_of_bot(available_bots, name):
    for champion in available_bots:
        if champion["name"] == name:
            return champion["id"]
    raise RuntimeError(f'Cannot find a bot by the name of "{name}".')

async def add_bot(connection, champion_id, team_id, difficulty):
    if team_id not in ["100", "200"]:
        raise ValueError(f'team_id={team_id}')

    if difficulty not in ["EASY", "MEDIUM"]:
        raise ValueError(f'difficulty={difficulty}')

    data = {
        "botDifficulty": difficulty,
        "championId": champion_id,
        "teamId": team_id
    }
    async with connection.post('/lol-lobby/v1/lobby/custom/bots', json=data) as response:
        if response.status != 204:
            raise RuntimeError(f'Cannot add bot with champion_id={champion_id} team_id={team_id} difficulty={difficulty}.')
        return await response.json()

async def add_bots(connection, available_bots, bots_red, bots_blue, default_difficulty):
    bot_count_red = len(bots_red)
    bot_count_blue = len(bots_blue)

    if bot_count_red > 4 or bot_count_red < 0:
        raise ValueError(f'bot_count_red={bot_count_red}')

    if bot_count_blue > 5 or bot_count_blue < 0:
        raise ValueError(f'bot_count_blue={bot_count_blue}')

    if default_difficulty not in ["EASY", "MEDIUM"]:
        raise ValueError(f'default_difficulty={difficulty}')

    bots = [(x, "100") for x in bots_red] + [(x, "200") for x in bots_blue]
    bots_with_difficulty = []
    for bot_str, team_id in bots:
        champion_name, delimiter, difficulty = bot_str.partition(':')
        if not difficulty:
            difficulty = default_difficulty
        bots_with_difficulty.append((champion_name, difficulty, team_id))

    taken_champs = set()
    for (champion_name, difficulty, team_id) in bots_with_difficulty:
        if champion_name != "?":
            taken_champs.add(champion_name)

    chosen_bots = set()
    while len(chosen_bots) < 9:
        bot = random.choice(available_bots)
        name = bot["name"]
        if name not in taken_champs:
            chosen_bots.add(name)

    futures = []
    for (champion_name, difficulty, team_id) in bots_with_difficulty:
        if champion_name == "?":
            champion_name = chosen_bots.pop()
        champion_id = get_champion_id_of_bot(available_bots, champion_name)
        future = add_bot(connection, champion_id, team_id, difficulty)
        futures.append(future)
    await asyncio.gather(*futures)

def determine_app_port_and_token():
    for proc in psutil.process_iter():
        if proc.name() == "LeagueClientUx.exe":
            break

    if not proc:
        raise RuntimeError("Cannot find LeagueClientUx.exe instance.")

    for arg in proc.cmdline():
        if arg.startswith('--app-port='):
            port = arg.split('=', 1)[1]
        elif arg.startswith('--remoting-auth-token='):
            token = arg.split('=', 1)[1]

    if port is None or token is None:
        raise RuntimeError("Cannot determine app port and token.")
    return (port, token)

async def main(difficulty, password, mode, bots, spectator_policy, port, token):
    bots_by_team = bots.split("|", 1)
    bots_red = bots_by_team[0].split()
    if len(bots_by_team) > 1:
        bots_blue = bots_by_team[1].split()

    base_url = f'https://127.0.0.1:{port}'

    async with aiohttp.ClientSession(base_url, connector=aiohttp.TCPConnector(ssl=False), auth=aiohttp.BasicAuth('riot', token)) as connection:
        lobby, available_bots = await asyncio.gather(
            create_lobby(connection, mode, "lobby", password, spectator_policy),
            get_available_bots(connection)
        )

        await add_bots(connection, available_bots, bots_red, bots_blue, difficulty, )

difficulty = ["EASY", "MEDIUM"][1]
password = "delete yuumi"
mode = ["CUSTOM", "PRACTICETOOL"][1]
spectator_policy = ["AllAllowed", "NotAllowed"][1]
bots = "? ? ? ?|? ? ? ? ?"

port, token = determine_app_port_and_token()
asyncio.run(main(difficulty, password, mode, bots, spectator_policy, port, token))