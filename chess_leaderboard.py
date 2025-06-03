import csv
import requests
import logging
from collections import defaultdict
from datetime import datetime

# --- Configuration ---

ALL_PLAYERS = ["jcorr92", "xensprinkles", "euratoole", "teamoth"]  # Replace with real usernames
HEADERS = {
    "User-Agent": "chess-leaderboard-script/1.0 (jcb.corr92@gmail.com)"
}
WIN_POINTS = 3
DRAW_POINTS = 1

# --- Logging Setup ---

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- API Helpers ---

def fetch_archives(username):
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    logger.info(f"Fetching archives for {username}")
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 403:
        logger.warning(f"Access denied for {username} (403). Check privacy settings.")
        return []
    response.raise_for_status()
    return response.json().get('archives', [])

def fetch_games(archive_url):
    logger.info(f"Fetching games from {archive_url}")
    response = requests.get(archive_url, headers=HEADERS)
    response.raise_for_status()
    return response.json().get('games', [])

# --- Game Parsing ---

def parse_daily_games(player, opponents, game_list):
    results = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0})
    archives = fetch_archives(player)

    for url in archives:
        try:
            games = fetch_games(url)
        except Exception as e:
            logger.warning(f"Failed to fetch from {url}: {e}")
            continue

        for game in games:
            if game.get("time_class") != "daily":
                continue

            white = game.get("white", {}).get("username", "").lower()
            black = game.get("black", {}).get("username", "").lower()
            result_white = game.get("white", {}).get("result", "")
            result_black = game.get("black", {}).get("result", "")
            end_time = game.get("end_time", 0)

            if player not in (white, black):
                continue

            opponent = black if white == player else white
            if opponent not in opponents:
                continue

            if player == white:
                player_result = result_white
                opponent_result = result_black
            else:
                player_result = result_black
                opponent_result = result_white

            if player_result == "win":
                outcome = "win"
                results[opponent]["wins"] += 1
            elif player_result in {"checkmated", "timeout", "resigned", "lose"}:
                outcome = "loss"
                results[opponent]["losses"] += 1
            elif "draw" in player_result or player_result == "stalemate":
                outcome = "draw"
                results[opponent]["draws"] += 1
            else:
                continue

            game_list.append({
                "player": player,
                "opponent": opponent,
                "outcome": outcome,
                "end_time": end_time,
                "url": game.get("url", "")
            })

    return results

# --- Leaderboard Aggregation ---

def create_leaderboard(players):
    total_stats = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0})
    game_list = []

    for user in players:
        logger.info(f"Parsing games for {user}")
        opponents = [p.lower() for p in players if p != user]
        results = parse_daily_games(user.lower(), opponents, game_list)

        for opponent, stats in results.items():
            total_stats[user]["wins"] += stats["wins"]
            total_stats[user]["losses"] += stats["losses"]
            total_stats[user]["draws"] += stats["draws"]

    for user, stats in total_stats.items():
        stats["games"] = stats["wins"] + stats["losses"] + stats["draws"]
        stats["points"] = stats["wins"] * WIN_POINTS + stats["draws"] * DRAW_POINTS

    return total_stats, game_list

# --- CSV Writers ---

def save_game_list_csv(game_list, filename="game_list.csv"):
    # Sort games by end_time
    sorted_games = sorted(game_list, key=lambda x: x["end_time"])
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Player", "Opponent", "Outcome", "Game URL"])
        for game in sorted_games:
            date = datetime.utcfromtimestamp(game["end_time"]).strftime("%Y-%m-%d")
            writer.writerow([date, game["player"], game["opponent"], game["outcome"], game["url"]])
    logger.info(f"Saved game list to {filename}")

def save_leaderboard_csv(leaderboard, filename="leaderboard.csv"):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Player", "Games", "Wins", "Draws", "Losses", "Points"])
        for player, stats in sorted(leaderboard.items(), key=lambda x: x[1]['points'], reverse=True):
            writer.writerow([
                player,
                stats["games"],
                stats["wins"],
                stats["draws"],
                stats["losses"],
                stats["points"]
            ])
        writer.writerow([])
        writer.writerow(["Legend"])
        writer.writerow([f"Win = {WIN_POINTS} points", f"Draw = {DRAW_POINTS} points"])

    logger.info(f"Saved leaderboard to {filename}")

# --- Main ---

def main():
    leaderboard, game_list = create_leaderboard(ALL_PLAYERS)
    save_game_list_csv(game_list)
    save_leaderboard_csv(leaderboard)

if __name__ == "__main__":
    main()

