#!/usr/bin/env python3

import aiohttp
import asyncio
import itertools
import psutil
import random
import sys

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

async def main(config, port, token):
    bots_by_team = config["bots"].split("|", 1)
    if len(bots_by_team) > 1:
        bots_red = bots_by_team[0].split()
        bots_blue = bots_by_team[1].split()
    else:
        bots_blue = bots_by_team[0].split()
        bots_red = []

    base_url = f'https://127.0.0.1:{port}'

    async with aiohttp.ClientSession(base_url, connector=aiohttp.TCPConnector(ssl=False), auth=aiohttp.BasicAuth('riot', token)) as connection:
        lobby, available_bots = await asyncio.gather(
            create_lobby(connection, config["mode"], config["lobby_name"], config["password"], config["spectator_policy"]),
            get_available_bots(connection)
        )

        await add_bots(connection, available_bots, bots_red, bots_blue, "MEDIUM")

def print_help(program_name):
    print(f'''{program_name} -h/--help -s/--specator-policy POLICY -p/--password PASSWORD -m/--mode MODE -l/--lobby-name LOBBYNAME TEAMS

A tool to create a custom game or practice tool lobby with multiple bots.
Bots on each team can be chosen randomly or by name at a given difficulty each.

USAGE:
   TEAMS      = "TEAM|TEAM"           Set red and blue teams.
              = "TEAM"                Set blue team only.
   TEAM       = "BOT BOT BOT BOT BOT" Set team's bots (0 to 4 for red, 0 to 5 for blue).
   BOT        = "CHAMPION:DIFFICULTY" Set a champion at the given difficulty.
              = "CHAMPION"            Set a champion at medium difficulty.
   CHAMPION   = "?"                   Set a random champion.
              = "Alistar"             Set a specific champion.
                Available champions: https://leagueoflegends.fandom.com/wiki/Bots#Available_Bots
   DIFFICULTY = "EASY" "MEDIUM"
   POLICY     = "AllAllowed" "NotAllowed"
   MODE       = "CUSTOM" "PRACTICETOOL"

EXAMPLES:
  Full random teams:
  {program_name} "? ? ? ?|? ? ? ? ?"

  Alistar on left team with you, 2 randoms on other:
  {program_name} "Alistar|? ?"

  1v1 against Brand:
  {program_name} "Brand"

  Own champs easy, opposing champs medium difficulty:
  {program_name} "?:EASY ?:EASY ?:EASY ?:EASY|? ? ? ? ?"
''')

def parse_args(config, argv):
    itr = itertools.pairwise(sys.argv[1:] + [None])
    for (k, v) in itr:
        print(f"Parsing {k} {v}")
        if k in ["-h", "--help"]:
            print_help(argv[0])
            return 0
        elif k in ["-s", "--spectator-policy"]:
            if v not in ["AllAllowed", "NotAllowed"]:
                print(f'Cannot parse specator policy "{v}". Expected "AllAllowed" or "NotAllowed".')
                return 1
            config["spectator_policy"] = v
        elif k in ["-p", "--password"]:
            config["password"] = "" if v is None else v
        elif k in ["-m", "--mode"]:
            if v not in ["CUSTOM", "PRACTICETOOL"]:
                print(f'Cannot parse game mode "{v}". Expected "CUSTOM" or "PRACTICETOOL".')
                return 1
            config["mode"] = v
        elif k in ["-l", "--lobby-name"]:
            if v is None or len(v) == 0:
                print("Expected lobby name")
                return 1
            config["lobby_name"] = v
        elif k.startswith('-'):
            print(f'Unknown command line argument "{k}".')
            return 1
        else:
            config["bots"] = k
    return None

config = {
    "password": "delete yuumi",
    "mode": ["CUSTOM", "PRACTICETOOL"][1],
    "spectator_policy": ["AllAllowed", "NotAllowed"][1],
    "bots": "? ? ? ?|? ? ? ? ?",
    "lobby_name": "lobby",
}
ret = parse_args(config, sys.argv)
if ret is not None:
    sys.exit(ret)

port, token = determine_app_port_and_token()
asyncio.run(main(config, port, token))