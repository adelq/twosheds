"""
twosheds.completer
~~~~~~~~~~~~~~~~~~

This module implements command completion.
"""
import os
import re
import sys
import traceback

from transform import transform


class Completer(object):
    """A Completer completes words when given a unique abbreviation.

    Type part of a word (for example ``ls /usr/lost``) and hit the tab key to
    run the completer.

    The shell completes the filename ``/usr/lost`` to ``/usr/lost+found/``,
    replacing the incomplete word with the complete word in the input buffer.

    .. note::

        Completion adds a ``/`` to the end of completed directories and a
        space to the end of other completed words, to speed typing and provide
        a visual indicator of successful completion. Completer.use_suffix can
        be set ``False`` to prevent this.

    If no match is found (perhaps ``/usr/lost+found`` doesn't exist), then no
    matches will appear.

    If the word is already complete (perhaps there is a ``/usr/lost`` on your
    system, or perhaps you were thinking too far ahead and typed the whole
    thing) a ``/`` or space is added to the end if it isn't already there.

    The shell will list the remaining choices (if any) below the unfinished
    command line whenever completion fails, for example::

        $ ls /usr/l[tab]
        lbin/       lib/        local/      lost+found/

    Completion will always happen on the shortest possible unique match, even
    if more typing might result in a longer match. Therefore::

        $ ls
        fodder   foo      food     foonly
        $ rm fo[tab]

    just beeps, because ``fo`` could expand to ``fod`` or ``foo``, but if we
    type another ``o``::

        $ rm foo[tab]
        $ rm foo

    the completion completes on ``foo``, even though ``food`` and ``foonly``
    also match.

    .. note::

        ``excludes_patterns`` can be set to a list of regular expression
        patterns to be ignored by completion.

        Consider that the completer were initialized to ignore
        ``[r'.*~', r'.*.o']``::

            $ ls
            Makefile        condiments.h~   main.o          side.c
            README          main.c          meal            side.o
            condiments.h    main.c~
            $ emacs ma[tab]
            main.c

    :param use_suffix: add a ``/`` to completed directories and a space to the
                       end of other completed words, to speed typing and
                       provide a visual indicator of successful completion.
                       Defaults to ``True``.
    :param excludes: a list of regular expression patterns to be ignored by
                     completion.
    :param extensions:
        A sequence of generators which can extend the matching capabilities of
        the completer. Generators must accept a string "word" as the sole
        argument, representing the word that the user is trying to complete,
        and use it to generate possible matches.
    """
    def __init__(self, transforms, use_suffix=True, exclude=None,
                 extensions=None):
        self.transforms = transforms
        self.use_suffix = use_suffix
        self.exclude_patterns = exclude or []
        self.extensions = extensions or []

    def complete(self, word, state):
        """Return the next possible completion for ``word``.

        This is called successively with ``state == 0, 1, 2, ...`` until it
        returns ``None``.

        The completion should begin with ``word``.

        :param word: the word to complete
        :param state: an int, used to iterate over the choices
        """
        try:
            import rl
            # TODO: doing this manually right now, but may make sense to
            # exploit
            rl.completion.suppress_append = True
        except ImportError:
            pass
        word = transform(word, self.transforms, word=True)
        try:
            match = self.get_matches(word)[state]
            return transform(match, self.transforms, word=True, inverse=True)
        except IndexError:
            return None

    def exclude_matches(self, matches):
        """Filter any matches that match an exclude pattern.

        :param matches: a list of possible completions
        """
        for match in matches:
            for exclude_pattern in self.exclude_patterns:
                if re.match(exclude_pattern, match) is not None:
                    break
            else:
                yield match

    def _is_hidden_file(self, filename):
        return filename.startswith('.')

    def gen_filename_completions(self, word, filenames):
        """Generate a sequence of filenames that match ``word``.

        :param word: the word to complete
        """
        match_found = False
        if word:
            for filename in filenames:
                if filename.startswith(word):
                    match_found = True
                    yield filename
        else:
            for filename in filenames:
                if not self._is_hidden_file(filename):
                    match_found = True
                    yield filename
        # return results that match anywhere in the file if no results are
        # found
        if not match_found:
            for filename in filenames:
                if word in filename:
                    yield filename

    def gen_matches(self, word):
        """Generate a sequence of possible completions for ``word``.

        :param word: the word to complete
        """

        if word.startswith("$"):
            for match in self.gen_variable_completions(word, os.environ):
                yield match
        else:
            head, tail = os.path.split(word)
            filenames = os.listdir(head or '.')
            for match in self.gen_filename_completions(tail, filenames):
                yield os.path.join(head, match)
        for extension in self.extensions:
            for match in extension(word):
                yield match

    def gen_variable_completions(self, word, env):
        """Generate a sequence of possible variable completions for ``word``.

        :param word: the word to complete
        :param env: the environment
        """
        # ignore the first character, which is a dollar sign
        var = word[1:]
        for k in env:
            if k.startswith(var):
                yield "$" + k

    def get_matches(self, word):
        """
        Get a list of filenames with match *word*.
        """
        matches = self.gen_matches(word)
        # defend this against bad user input for regular expression patterns
        try:
            matches = self.exclude_matches(matches)
        except Exception:
            sys.stderr.write(traceback.format_exc())
            return None
        else:
            if self.use_suffix:
                matches = [self.inflect(match) for match in matches]
            return list(matches)

    def inflect(self, filename):
        """Inflect a filename to indicate its type.

        If the file is a directory, the suffix "/" is appended, otherwise
        a space is appended.

        :param filename: the name of the file to inflect
        """
        suffix = ("/" if os.path.isdir(filename) else " ")
        return self._escape(filename) + suffix

    def _escape(self, path):
        """Escape any spaces in *path*."""
        return path.replace(" ", "\\ ")


def make_completer(transforms, use_suffix=True, exclude=None):
    try:
        import rl
    except ImportError:
        import warnings
        warnings.warn("rl unavailable")
        import pprint
        pprint.pprint(os.environ["PYTHONPATH"])
        return None
    else:
        completer = Completer(transforms, use_suffix, exclude)
        rl.completer.completer = completer.complete
        rl.completer.parse_and_bind('TAB: complete')
        # rl.completion.filename_completion_desired = True
        rl.completer.word_break_characters = (rl.completer
                                              .word_break_characters
                                              .replace("-", "")
                                              .replace("~", "")
                                              .replace("$", "")
                                              .replace("/", "")
                                              )
        return completer
