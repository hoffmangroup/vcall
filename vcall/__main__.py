#!/usr/bin/env python

"""vcall: recursively run version control commands.

Run version control commands in multiple subdirectories.
COMMAND is one of: status, update, upgrade.
Version control systems supported: CVS, Subversion, Mercurial.
"""

__version__ = "0.1.0a3"

# Copyright 2008, 2013-2016, 2019, 2020 Michael M. Hoffman

from configparser import (NoSectionError, NoOptionError, SafeConfigParser)
from os import getenv, walk
from pathlib import Path
import re
from shlex import split
import sys

from optbuild import (Cwd, OptionBuilder, OptionBuilder_LongOptWithSpace,
                      OptionBuilder_ShortOptWithSpace, ReturncodeError)

from tqdm import tqdm, tqdm_gui

if getenv("DISPLAY"):
    PROGRESSERS = [tqdm_gui]
else:
    PROGRESSERS = None

GIT_PROG = OptionBuilder("git")
HG_PROG = OptionBuilder_LongOptWithSpace("hg")
SVN_PROG = OptionBuilder("svn")
CVS_PROG = OptionBuilder_ShortOptWithSpace("cvs")

CVS_KWARGS_DEFAULT = dict(q=True)  # quiet

RC_FILENAME = ".vcallrc"

VERBOSE = True

def progress(iterable, *args, **kwargs):
    """Try starting different progressers until one works."""
    if not PROGRESSERS:
        return iterable

    for progresser in PROGRESSERS:
        try:
            return progresser(iterable, *args, **kwargs)
        except RuntimeError:
            pass


def make_args(command, subcommand, dirname):
    """Make arguments for `subcommand`."""
    if subcommand is not None:
        return [command, subcommand, dirname]
    else:
        return [command, dirname]


def parse_config(dirname):
    """Parse configuration for `dirname`."""
    config = SafeConfigParser(dict(dirname=dirname))
    config.read(Path(dirname) / RC_FILENAME)

    return config


def get_config_args(prog, subcommand, dirname):
    """Get arguments for `prog` `subcommand` in `dirname`."""
    config = parse_config(dirname)

    if sys.stdin.isatty():
        section = "interactive"
    else:
        section = "noninteractive"

    option = "%s.%s" % (prog.prog, subcommand)  # ex: hg.summary

    try:
        value = config.get(section, option)
    except NoSectionError:
        return
    except NoOptionError:
        return

    return split(value)


def try_prog(prog, funcname, dirname, *args, **kwargs):
    """Try running `prog` via `funcname` in `dirname`."""
    config_args = get_config_args(prog, args[0], dirname)
    if config_args is not None:
        args = config_args
        kwargs = {}

    try:
        return getattr(prog, funcname)(*args, **kwargs)
    except ReturncodeError:
        msg = "Error detected from %s in %s; repeating" % (prog, dirname)
        print(msg, file=sys.stderr)
        prog(*args, **kwargs)
    except OSError:
        msg = "Error detected trying to run %s in %s" % (prog, dirname)
        print(msg, file=sys.stderr)
        raise


def output_lines(output):
    """Get lines from `output`."""
    if output:
        # XXX: not the right place to do unicode conversion
        # should be done in optbuild
        return output.decode().splitlines()

    return []


def print_except(output, regex, dirname=None):
    """Print output except anything matching `regex`.

    Return whether any output was produced.
    """
    res = False

    if dirname:
        prefix = "%s:" % dirname
    else:
        prefix = ""

    for line in output_lines(output):
        if not regex.match(line):
            res = True
            print(prefix, line, file=sys.stderr)

    return res


re_cvs_new_directory_ignored = re.compile(r"^cvs update: New directory `.*'"
                                          " -- ignored$")


def run_cvs(command, dirname):
    """
    Run CVS `command` in `dirname`.

    cvs -n update has a bug where it will print things like

      cvs update: New directory `search_spectrum_out' -- ignored

    for any directory that has been deleted in the repository. For more
    info Google [cvs-info "new directory" ignored]. I can't figure out a
    way to suppress this, except to actually delete things locally.
    """
    subcommand = None
    kwargs = CVS_KWARGS_DEFAULT.copy()

    if command == "upgrade":
        return

    if command == "status":
        command = "update"
        kwargs["n"] = True  # don't do anything on disk

    if command == "update":
        subcommand = "-dP"

    # relpath avoids "absolute pathname ... illegal for server" error
    args = make_args(command, subcommand, ".")

    output, error = try_prog(CVS_PROG, "getoutput_error", dirname,
                             Cwd(dirname), *args, **kwargs)

    res = False
    if output:
        print(output, end="")
        res = True

    res = print_except(error, re_cvs_new_directory_ignored) or res

    return res


re_svn_status_against = re.compile(r"^Status against revision:")


def run_svn(command, dirname):
    """Run Subversion `command` in `dirname`."""
    subcommand = None
    if command == "status":
        subcommand = "-u"

    args = make_args(command, subcommand, dirname)

    output = try_prog(SVN_PROG, "getoutput", dirname, *args)
    return print_except(output, re_svn_status_against)


re_hg_quiet_summary = re.compile(r"^(?!(?:commit|update|remote): )"
                                 r"|(?:commit: \(clean\)|update: \(current\)"
                                 r"|remote: \(synced\))$")
re_hg_0_updates = re.compile(r"^0 files updated, 0 files merged,"
                             " 0 files removed, 0 files unresolved$")


def run_hg(command, dirname):
    """Run Mercurial `command` in `dirname`."""
    kwargs = dict(cwd=dirname)

    if command == "status":
        args = ["summary"]
        try:
            HG_PROG("paths", "default", quiet=True, **kwargs)
        except ReturncodeError as err:
            if err.returncode != 1:
                raise
        else:
            args.append("--remote")
    elif command == "upgrade":
        return
    elif command == "update":
        try:
            HG_PROG("pull", quiet=True, **kwargs)
        except ReturncodeError as err:
            # exit status 1 when there is nothing new incoming
            if err.returncode != 1:
                raise

        output = try_prog(HG_PROG, "getoutput", dirname, "update", cwd=dirname)
        print_except(output, re_hg_0_updates, dirname)

        return
    else:
        args = [command]

    output = try_prog(HG_PROG, "getoutput", dirname, *args, **kwargs)
    return print_except(output, re_hg_quiet_summary, dirname)


re_git_fetching_origin = re.compile(r"^Fetching origin$")
re_git = re.compile(r"XXXcanthappenneedsomethingbetterhereXXX") # XXX


def run_git(command, dirname):
    """Run Git `command` in `dirname`."""
    args_dirname = ["-C", dirname]

    if command == "status":
        args_remote_update = args_dirname + ["remote", "update"]
        output, error = try_prog(GIT_PROG, "getoutput_error", dirname, *args_remote_update)
        print_except(error, re_git_fetching_origin, dirname)

        args = args_dirname + ["status", "--porcelain"]
    else:
        raise NotImplementedError

    output = try_prog(GIT_PROG, "getoutput", dirname, *args)
    return print_except(output, re_git, dirname)


RUNNERS = {".git": run_git,
           ".hg": run_hg,
           ".svn": run_svn,
           "CVS": run_cvs}


def walk_dirname(command, dirname):
    """Walk `dirname` with `command`."""
    # top-down, does directory before its subdirectories
    walker = walk(dirname)

    if sys.stdout.isatty():
        walker = progress(walker, f" {dirname}", unit=" dir")

    for branch_dirname, child_dirnames, child_filenames in walker:
        for signature_dirname, runner in RUNNERS.items():
            # check for signature of any version control system
            if signature_dirname in child_dirnames:
                try:
                    if VERBOSE:
                        print(f"* {runner.__name__} {command}: {branch_dirname}", file=sys.stderr)
                    if runner(command, branch_dirname):
                        yield branch_dirname
                except ReturncodeError:
                    pass  # error reported to user by runner

                break


def _vcall(command, dirnames):
    affected_dirnames = []

    walker = progress(dirnames, "directories", unit=" dir")
    for dirname in walker:
        affected_dirnames.extend(walk_dirname(command, dirname))

    if affected_dirnames:
        print()
        print(sys.argv[0], "update", *affected_dirnames)


def vcall(command="status", dirnames=[]):
    """Run version control `command` on `dirnames`."""
    if not dirnames:
        dirnames = ["."]

    if command.startswith("st"):
        command = "status"
    elif command.startswith("upg"):
        command = "upgrade"
    elif command.startswith("up"):
        command = "update"

    return _vcall(command, dirnames)


def parse_options(args):
    """Parse options in `args`."""
    # XXX: should switch to argparse to get RawDescriptionHelpFormatter

    from optparse import OptionParser

    usage = "%prog [OPTION...] COMMAND [DIR...]"
    version = "%%prog %s" % __version__
    doclines = __doc__.splitlines()
    long_description = "\n".join(doclines[2:])

    parser = OptionParser(usage=usage, version=version,
                          description=long_description)

    options, args = parser.parse_args(args)

    if len(args) < 1:
        parser.error("incorrect number of arguments")

    return options, args


def main(args=sys.argv[1:]):
    """Run from command line with `args`."""
    options, args = parse_options(args)

    return vcall(args[0], args[1:])


if __name__ == "__main__":
    sys.exit(main())
