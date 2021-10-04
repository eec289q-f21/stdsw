#!/usr/bin/env python3

import argparse
from os import path
import sys

from common.resources import JsonLoader

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from common.configuration import AWSPathManager, AWSInfra
from taskmgmt.runnable import IOTaskRunner



if __name__ == '__main__':
    aws_parser = argparse.ArgumentParser(description='Uploads your files to S3Bucket',
                                         epilog='Enjoy the program! :)')
    # aws config
    aws_cfg_arg = aws_parser.add_mutually_exclusive_group(required=True)

    aws_cfg_arg.add_argument('--configurl',
                             action='store_const',
                             const="https://raw.githubusercontent.com/eec-ucd/eec289/main/config.aws",
                             help='configuration url for the aws server')

    aws_cfg_arg.add_argument('--configfile',
                             action='store_const',
                             const='config.aws',
                             help='configuration file for the aws server')

    aws_parser.add_argument('--task',
                            type=str,
                            required=True,
                            help="File the task is encoded in json")

    args = aws_parser.parse_args()

    if args.configurl:
        data = JsonLoader.load_url(args.configurl)

    if args.configfile:
        data = JsonLoader.load_file(args.configfile)

    aws_path_manager = AWSPathManager(AWSInfra.load(data))

    IOTaskRunner(args.task, aws_path_manager).run()
