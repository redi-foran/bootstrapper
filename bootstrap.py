import argparse
import commands


parser = argparse.ArgumentParser()
commands._add_commands(parser.add_subparsers(title='commands'))

args = parser.parse_args()
args.callback(args)
