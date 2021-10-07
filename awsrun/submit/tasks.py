import os
import time
from abc import ABC, abstractmethod

from common.commands import Compress, Upload, SendMsg, Download, Decompress
from common.configuration import AWSPathManager
from common.protocol import IOTask, AWSMsg, AWSIDRegistration
from common.resources import Folder, File, OSPath
from multipledispatch import dispatch


class Issuer(ABC):
    @abstractmethod
    def issue(self, task: AWSMsg):
        pass


class AWSIssuer(Issuer):
    def __init__(self, aws_path_manager: AWSPathManager):
        self._aws_path_manager = aws_path_manager

    @staticmethod
    def dependencies(task: IOTask):
        deps = []
        cwd = Folder.cwd()
        deps.extend(map(lambda f: cwd.relative(f),
                        map(lambda p: OSPath.new(p), filter(lambda arg: os.path.exists(arg), task.command.shell))))
        deps.extend(map(lambda f: cwd.relative(f), task.command.deps))
        return deps

    def _operands(self, task: IOTask):
        resources = Compress(task.workspace.input, *AWSIssuer.dependencies(task)).execute()
        uploaded = Upload(self._aws_path_manager.server_path, self._aws_path_manager.bucket_path, resources).execute()
        # Echo status back to user.
        print("Resources {0} is transfered\n".format(uploaded.path))
        time.sleep(1)

    def _operator(self, task: IOTask):
        return SendMsg(self._aws_path_manager.server_path, self._aws_path_manager.taskq_path, task).execute()

    def _clean_files(self, task: IOTask):
        if os.path.exists(task.workspace.local_input):
            os.remove(task.workspace.local_input)
        if os.path.exists(task.workspace.local_output):
            os.remove(task.workspace.local_output)

    def _output(self, task: IOTask):
        retrieved = Download(self._aws_path_manager.server_path, self._aws_path_manager.bucket_path, task.workspace.output,
                             task.command.timeout).execute()
        if retrieved:
            cwd = Folder(os.path.normpath(os.getcwd()))
            # files to extract
            stdout_report = File('stdout')
            stderr_report = File('stderr')
            target = Decompress(cwd, retrieved, stdout_report, stderr_report).execute()
            # report
            File.new(target.relative(stdout_report)).content(header=" STDOUT ")
            File.new(target.relative(stderr_report)).content(header=" STDERR ")
            #
            if task.perf_file:
                Decompress(task.lwd.relative(task.workspace.root).create(), task.workspace.local_input).execute()
            print("Task executed successfully")
        else:
            print("failed to retrieve, re-submit the job!!!")
        self._clean_files(task)


    @dispatch(IOTask)
    def issue(self, task):
        self._operands(task)
        self._operator(task)
        self._output(task)

    @dispatch(AWSIDRegistration)
    def issue(self, reg):
        SendMsg(self._aws_path_manager.server_path, self._aws_path_manager.regq_path, reg, True).execute()
