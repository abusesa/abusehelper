import botnet
import commands

Botnet = botnet.Botnet
Command = botnet.Command


def main():
    try:
        botnet = Botnet()
        botnet.load_module(commands)
        botnet.run()
    except KeyboardInterrupt:
        pass
