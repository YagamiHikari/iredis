# -*- coding: utf-8 -*-
import os
import sys
import logging
from pathlib import Path

import redis
import click
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.styles import Style
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.styles import Style

from .client import Client
from .renders import render_dict
from .redis_lexer import RedisLexer


logging.basicConfig(
    filename="iredis.log",
    filemode="a",
    format="%(levelname)5s %(message)s",
    level="DEBUG",
)
logger = logging.getLogger(__name__)

HISTORY_FILE = Path(os.path.expanduser("~")) / ".iredis_history"
STYLE = Style.from_dict(
    {
        # User input (default text).
        "": "",
        # Prompt.
        "hostname": "",
    }
)


def create_grammar():
    return compile(
        r"""
        (\s*  (?P<command_key>(HGETALL|GET))   \s+   (?P<key>[0-9.]+)   \s*) |
        (\s*  (?P<command_key_value>(SET|KSET))   \s+   (?P<key>[0-9.]+)   \s+   (?P<value>[0-9.]+)   \s*) 
    """
    )

example_style = Style.from_dict({
    'operator':       '#33aa33 bold',
    'number':         '#ff0000 bold',

    'trailing-input': 'bg:#662222 #ffffff',
})

g = create_grammar()

lexer = GrammarLexer(g, lexers={
    'command_key_value': SimpleLexer('class:pygments.keyword'),
    'command_key': SimpleLexer('class:pygments.keyword'),
    'key': SimpleLexer('class:operator'),
    'value': SimpleLexer('class:number'),
})

# Can all grammer have only 1 token, and completer based on lexer?
completer = GrammarCompleter(g, {
    'command_key_value': WordCompleter(["HGETALL", "GET", "MGET"]),
    'command_key': WordCompleter(["AGET", "AZZ", "AOK"]),
})

def repl(client, session):
    while True:
        logger.debug("REPL waiting for command...")
        try:
            command = session.prompt(
                "{hostname}> ".format(hostname=str(client)),
                style=example_style,
                lexer=lexer,
                completer=completer
            )
        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt!")
            continue
        except EOFError:
            print("Goodbye!")
            sys.exit()
        logger.info(f"Command: {command}")

        # blank input
        if not command:
            continue

        try:
            answer = client.send_command(command)
        # Error with previous command or exception
        except Exception as e:
            print("(error)", str(e))

        # Fine with answer
        else:
            print(answer)


# command line entry here...
@click.command()
@click.pass_context
@click.option("-h", help="Server hostname", default="127.0.0.1")
@click.option("-p", help="Server port", default="6379")
@click.option("-n", help="Database number.", default="0")
def gather_args(ctx, h, p, n):
    logger.info(f"iredis start, host={h}, port={p}, db={n}.")
    return ctx


def main():
    # invoke in non-standalone mode to gather args
    ctx = gather_args.main(standalone_mode=False)
    if not ctx:  # called help
        return

    # Create history file if not exists.
    if not os.path.exists(HISTORY_FILE):
        logger.info(f"History file {HISTORY_FILE} not exists, create now...")
        f = open(HISTORY_FILE, "w+")
        f.close()

    session = PromptSession(history=FileHistory(HISTORY_FILE))

    client = Client(**ctx.params)
    repl(client, session)
