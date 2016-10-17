#!/usr/bin/python3
import argparse
import sys
import commands


def create_argument_parser():
    parser = argparse.ArgumentParser()
    commands.add_commands(parser.add_subparsers(title='commands'))
    return parser


def main(args):
    parsed_args = create_argument_parser().parse_args(args)
    parsed_args.callback(parsed_args)


if __name__ == "__main__":
    main(sys.argv[1:])
