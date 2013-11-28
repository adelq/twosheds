import atexit
import code
import logging
import os
import readline
from subprocess import call, check_output
import sys
import traceback

LAST = '_'
HOME = os.environ["HOME"]


def run_python(line, env):
    try:
        return eval(line, env, env)  # expressions
    except SyntaxError:
        exec(line, env, env)  # statements


class Shell(object):
    BUILTINS = {'cd': os.chdir}

    def __init__(self, env, aliases=None, builtins=None,
                 histfile=os.path.expanduser("~/.console-history")):
        self.env = env
        self.aliases = aliases or {}
        self.builtins = builtins or self.BUILTINS
        self.init_history(histfile)

    @property
    def prompt(self):
        pwd = check_output("pwd")
        return (pwd.strip() + " ").replace(HOME, "~")

    def out(self, msg):
        sys.stdout.write(msg)

    def error(self, msg):
        sys.stderr.write(msg)

    def read(self):
        try:
            return self.rewrite(raw_input(self.prompt))
        except EOFError:
            raise SystemExit()

    def rewrite(self, line):
        tokens = line.split()
        new_tokens = []
        for token in tokens:
            try:
                v = self.aliases[token]
            except KeyError:
                if token.startswith("$"):
                    try:
                        v = os.environ[token[1:]]
                    except KeyError:
                        new_tokens.append(token)
                    else:
                        new_tokens.append(v)
                else:
                    new_tokens.append(token)
            else:
                new_tokens.append(v)
        return " ".join(new_tokens)

    def _raise_cursor(self, n=1):
        """Move the cursor up `n` lines."""
        self.out('\033[%sA' % n)
        sys.stdout.flush()

    def _clear_line(self):
        self.out('\033[K')
        sys.stdout.flush()

    def eval(self, line):
        if line:
            exit_code = call(line, shell=True)

    def interact(self):
        while True:
            try:
                line = self.read()
                tokens = line.split()
                command, args = tokens[0], tokens[1:]
                # handle any shell builtin commands
                try:
                    self.builtins[command](args[0])
                except KeyError:
                    rv = self.eval(line)
                else:
                    continue
            except SystemExit:
                break
            except:
                self.error(traceback.format_exc())
            else:
                if rv is not None:
                    self.env[LAST] = rv
                    self.out(str(rv))

    def complete(self, text, state):
        matches = []

        head, tail = os.path.split(text)

        ls = check_output("ls %s" % head, shell=True)
        filenames = ls.split()

        for filename in filenames:
            if filename.startswith(tail):
                matches.append(os.path.join(head, filename))
        try:
            return matches[state]
        except IndexError:
            return None

    def init_history(self, histfile):
        if sys.platform == 'darwin':
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        readline.set_completer(self.complete)
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(histfile)
            except IOError:
                pass
            atexit.register(self.save_history, histfile)

    def save_history(self, histfile):
        readline.write_history_file(histfile)


class PythonShell(Shell):
    def eval(self, line):
        if line:
            exit_code = call(line, shell=True)
            if exit_code != 0:
                # hide the error
                self._raise_cursor()
                self._clear_line()
                return run_python(line, self.env)
