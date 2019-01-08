#!/usr/bin/python

"""
This is a simple tool to replace text variable references with 
concrete values

=====

Variables set by default:
${def_var_str}

Blame (most) bugs on: Martin Kjellstrand <martin.kjellstrand@madworx.se>.
"""

# todo: rename to kicad-tools

import os
import pcbnew
import re
import glob
from argparse import RawTextHelpFormatter
import argparse
import sys
import textwrap as _textwrap
import logging
import collections
from itertools import imap
import time
import inspect
# TODO: Delay this loading.
from setuptools_scm import get_version

logger = logging.getLogger()
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

class Variables(object):
    def __init__(self):
        self.vars = {}
    def REV(self):
        """Current SCM revision of project"""
        return "kalle test \" foo bar"
    def DATE(self):
        """Current (todays) date"""
        return time.strftime(args.date_format)
    def FILENAME(self):
        """pcbnew filename"""
        return os.path.basename(input_file)
    def DOC_TITLE(self):
        """Document `Title' set in file"""
        return board.GetTitleBlock().GetTitle()
    def DOC_COMPANY(self):
        """Document `Company' set in file"""
        return board.GetTitleBlock().GetCompany()
    def _set(self,name,value):
        logger.log(logging.DEBUG, "Setting variable [{}] => [{}]".format(name,value))
        self.vars[name] = value
    def __call__(self, name):
        return self.vars[name]

class SetVarAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        m = re.split(r':', values)
        vars._set(m[0],m[1])

vars = Variables()

dvars = {}
for variable in inspect.getmembers(Variables, predicate=inspect.ismethod):
    if variable[0][0] != '_':
        dvars[variable[0]] = inspect.getdoc(getattr(Variables,variable[0]))
def_var_str = ""
for var in collections.OrderedDict(sorted(dvars.items())):
    def_var_str += "  - {0:<{1}}    = {2}\n".format(var,max(imap(len,dvars)),dvars[var])

docstr = re.sub(r'\${([^}]+)}', lambda m : globals()[m.group(1)], __doc__)
docparts = re.match(r'^(.*)\s*\r?\n=====\r?\n\s*(.+)$', docstr, re.DOTALL)
if docparts is None:
    raise AssertionError("Could not parse docstring.")

parser = argparse.ArgumentParser(description=docparts.group(1),
                                 epilog=docparts.group(2),
                                 formatter_class=RawTextHelpFormatter)

parser.add_argument('file', metavar='<file/dir>', nargs='+',
                    type=str,
                    help='Pcbnew board file (.kicad_pcb), or a directory\n'
                         'containing one or more Pcbnew files.')

parser.add_argument('-c', '--clobber', action='store_true',
                    dest='clobber', default=False,
                    help='Allow input files to be overwritten.')

parser.add_argument('-o',
                    dest='output_dir', type=str, metavar='<file/dir>',
                    default='.',
                    help='Put generated files into this directory.\n'
                         '(Default is current working directory)')

parser.add_argument('--rev-format',
                    dest='rev-format', type=str,
                    help='SCM revision output format.')

parser.add_argument('--date-format', default='%Y-%m-%d',
                    dest='date_format', type=str,
                    help='Date formatting (strftime syntax)')


parser.add_argument('--var', action=SetVarAction,
                    dest='variable', type=str, metavar='<NAME:VALUE>',
                    help='Set additional (or overwrite existing)\n'
                         'variables to be expanded.')

args = parser.parse_args()

# Validate that output directory, or at least parent path exists:
if not os.path.exists(args.output_dir):
    assert os.path.exists(os.path.abspath(os.path.join(args.output_dir, os.pardir)))

# Materialize input arguments into a concrete list of files:
input_files = []
for path in args.file:
    if not os.path.exists(path):
        raise AssertionError("Provided file/dir `{0}' doesn't exist.".format(path))
    elif os.path.isdir(path):
        dir_files = glob.glob(os.path.join(path,'*.kicad_pcb'))
        if not dir_files:
            raise AssertionError("Provided directory `{0}' doesn't contain any .kicad_pcb files.".format(path))
        input_files.extend(dir_files)
    else:
        if not re.match(r'.*[.]kicad_pcb$', path):
            raise AssertionError("Provided file `{0}' doesn't have .kicad_pcb extension".format(path))
        input_files.append(path)

def perform_variable_expansion(variables,board):
    done = False
    while not done:
        done = True
        for draw in board.GetDrawings():
            if type(draw) == pcbnew.TEXTE_PCB:
                logger.log(logging.DEBUG, "Found text `{0}'".format(draw.GetText()))
                m = re.match(r'(.*)\${([A-Za-z0-9_-]+)}(.*)', draw.GetText(), re.MULTILINE)
                if m:
                    val = getattr(vars, m.group(2))()
                    logger.log(logging.DEBUG, "Translating ${{{0}}} -> `{1}'".format(m.group(2),val))
                    draw.SetText(m.group(1) + val + m.group(3))
                    done = False

for input_file in input_files:
    logger.log(logging.INFO, "Processing `{0}'.".format(input_file))
    absinput  = os.path.abspath(input_file)
    absoutput = os.path.abspath(os.path.join(args.output_dir, os.path.basename(input_file)))
    if absinput == absoutput and args.clobber is False:
        raise AssertionError("Will not overwrite input file `{0}' with output of same path.".format(input_file))
    board = pcbnew.LoadBoard(input_file)
    perform_variable_expansion(vars,board)
    logger.log(logging.DEBUG, "Will write output to {0}".format(absoutput))
    pcbnew.SaveBoard(absoutput,board)
