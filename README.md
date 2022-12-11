main.py -h/--help -s/--specator-policy POLICY -p/--password PASSWORD -m/--mode MODE -l/--lobby-name LOBBYNAME TEAMS

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
  main.py "? ? ? ?|? ? ? ? ?"

  Alistar on left team with you, 2 randoms on other:
  main.py "Alistar|? ?"

  1v1 against Brand:
  main.py "Brand"

  Own champs easy, opposing champs medium difficulty:
  main.py "?:EASY ?:EASY ?:EASY ?:EASY|? ? ? ? ?"

