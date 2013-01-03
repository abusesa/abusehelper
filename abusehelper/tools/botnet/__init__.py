import botnet
import commands

Botnet = botnet.Botnet
Command = botnet.Command


def main():
    botnet = Botnet()
    botnet.load_module(commands)
    botnet.run()
