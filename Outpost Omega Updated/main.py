"""Outpost Omega: Alien Siege - entry point.

Run from this folder:
    python main.py
"""
from game.game_manager import GameManager


def main():
    GameManager().run()


if __name__ == "__main__":
    main()
