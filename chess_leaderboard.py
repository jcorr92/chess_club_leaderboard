import csv
import requests
import logging
from collections import defaultdict
from datetime import datetime

# --- Configuration ---
ALL_PLAYERS = ["jcorr92", "xensprinkles", "euratoole", "teamoth"]
HEADERS = {
    "User-Agent": "chess-leaderboard-script/1.0 (jcb.corr92@gmail.com)"
}
WIN_POINTS = 3
DRAW_POINTS = 1
ROLLING_GAME_COUNT = 30

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
            else:
                player_result = result_black

            if player_result == "win":
                outcome = "win"
            elif player_result in {"checkmated", "timeout", "resigned", "lose"}:
                outcome = "loss"
            elif "draw" in player_result or player_result == "stalemate":
                outcome = "draw"
            else:
                continue

            game_list.append({
                "player": player,
                "opponent": opponent,
                "outcome": outcome,
                "end_time": end_time,
                "url": game.get("url", "")
            })

# --- Leaderboard Aggregation ---
def compute_leaderboard(game_list):
    stats = defaultdict(lambda: {"games": 0, "wins": 0, "draws": 0, "losses": 0})
    for game in game_list:
        player = game["player"]
        outcome = game["outcome"]
        stats[player]["games"] += 1
        if outcome == "win":
            stats[player]["wins"] += 1
        elif outcome == "draw":
            stats[player]["draws"] += 1
        elif outcome == "loss":
            stats[player]["losses"] += 1

    for player, s in stats.items():
        s["points"] = s["wins"] * WIN_POINTS + s["draws"] * DRAW_POINTS
        s["ppg"] = round(s["points"] / s["games"], 2) if s["games"] else 0.0

    return stats

# --- CSV Writers ---
def save_game_list_csv(game_list, filename="game_list.csv"):
    sorted_games = sorted(game_list, key=lambda x: x["end_time"])
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Player", "Opponent", "Outcome", "Game URL"])
        for game in sorted_games:
            date = datetime.utcfromtimestamp(game["end_time"]).strftime("%Y-%m-%d")
            writer.writerow([date, game["player"], game["opponent"], game["outcome"], game["url"]])
    logger.info(f"Saved game list to {filename}")

def write_leaderboard_section(writer, title, stats):
    writer.writerow([title] + [""] * 5)
    writer.writerow(["Player", "Games", "Wins", "Draws", "Losses", "Points"])
    for player, s in sorted(stats.items(), key=lambda x: x[1]['points'], reverse=True):
        writer.writerow([player, s["games"], s["wins"], s["draws"], s["losses"], s["points"]])
    writer.writerow([])
    #
    # writer.writerow(["Weighted Leaderboard (Points per Game)"])
    # writer.writerow(["Player", "Games", "Points", "Points/Game"])
    # for player, s in sorted(stats.items(), key=lambda x: x[1]['ppg'], reverse=True):
    #     writer.writerow([player, s["games"], s["points"], s["ppg"]])
    # writer.writerow([])

def save_leaderboard_csv(full_game_list, filename="leaderboard.csv"):
    full_sorted = sorted(full_game_list, key=lambda x: x["end_time"])
    rolling = full_sorted[-ROLLING_GAME_COUNT:]

    total_stats = compute_leaderboard(full_sorted)
    rolling_stats = compute_leaderboard(rolling)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        write_leaderboard_section(writer, f"Rolling Leaderboard (Last {ROLLING_GAME_COUNT} Games)", rolling_stats)
        write_leaderboard_section(writer, "Total Leaderboard", total_stats)
    logger.info(f"Saved leaderboard to {filename}")

# --- Main ---
def main():
    all_game_list = []
    for user in ALL_PLAYERS:
        logger.info(f"Processing games for {user}")
        parse_daily_games(user.lower(), [p.lower() for p in ALL_PLAYERS if p != user.lower()], all_game_list)

    save_game_list_csv(all_game_list)
    save_leaderboard_csv(all_game_list)

if __name__ == "__main__":
    main()
