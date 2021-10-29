#!/usr/bin/env python3
import argparse
from os import path
import sys
from functools import reduce

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from common.resources import JsonLoader
from common.configuration import CmdConfig, WSConfig, AWSPathManager, AWSInfra
from common.protocol import IOTask
from submit.tasks import AWSIssuer


class CoreRange:
    def __init__(self, imin=1, imax=1):
        self.imin = imin
        self.imax = imax

    def __call__(self, arg):
        try:
            value = int(arg)
        except ValueError:
            raise argparse.ArgumentTypeError("Must be an integer")

        if self.imin < 0 or self.imax < 0:
            raise argparse.ArgumentTypeError(f"Core numbers can only be positive")

        """
        if value < self.imin:
            raise argparse.ArgumentTypeError(f"Must be an integer >= {self.imin}")

        if value > self.imax:
            raise argparse.ArgumentTypeError(f"Must be an integer <= {self.imax}")
        """

        if not (value == self.imin or value == self.imax):
            raise argparse.ArgumentTypeError("For now we only support {} and {} cores".format(self.imin,self.imax))

        return value


if __name__ == '__main__':
    aws_parser = argparse.ArgumentParser(description='Runs your program on AWS',
                                         epilog='Enjoy the program! :)')
    # aws config
    awscfg = aws_parser.add_mutually_exclusive_group(required=True)

    awscfg.add_argument('--configurl',
                        action='store_const',
                        const="https://raw.githubusercontent.com/eec-ucd/eec289/main/config.aws",
                        help='configuration url for the aws server')

    awscfg.add_argument('--configfile',
                        action='store_const',
                        const='config.aws',
                        help='configuration file for the aws server')

    aws_parser.add_argument('--deps',
                            type=str,
                            default="deps.aws",
                            help='config file holding the relative paths')

    aws_parser.add_argument('--workfolder',
                            type=str,
                            default="/tmp/std-submissions",
                            help='work folder')

    aws_parser.add_argument('--timeout',
                            type=int,
                            default=60,
                            help='task timeout')

    aws_parser.add_argument('--perf',
                            type=str,
                            default="",
                            help='performance')

    aws_parser.add_argument('--core',
                            type=CoreRange(1, 8),
                            default=1,
                            help='is this a multicore run')
    # workspace config
    aws_parser.add_argument('--prefix',
                            type=str,
                            default="submission",
                            help='prefix for job folders')

    aws_parser.add_argument('--env',
                            type=str,
                            default="",
                            help='environment variables')

    # task config
    aws_parser.add_argument('--cmd',
                            nargs='+',
                            required=True,
                            help='command to run (executable with arguments)')

    args = aws_parser.parse_args()

    if args.configurl:
        data = JsonLoader.load_url(args.configurl)

    if args.configfile:
        data = JsonLoader.load_file(args.configfile)

    aws_path_manager = AWSPathManager(AWSInfra.load(data))
    cmd_config = CmdConfig.new(cmd=reduce(list.__add__, map(lambda s: s.split(' '), args.cmd)),
                               timeout=args.timeout,
                               cores=args.core,
                               depfile=args.deps,
                               env=args.env.split(';'))

    ws_config = WSConfig.new(args.prefix)

    issuer = AWSIssuer(aws_path_manager)

    task = IOTask.new(cmd_config, ws_config, args.workfolder, args.perf)

    issuer.issue(task)
