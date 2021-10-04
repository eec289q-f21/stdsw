import json
import logging
import io
import os
import signal
import subprocess
import tarfile
from abc import ABC, abstractmethod

import objectfactory

from common.commands import Download, Decompress, Upload
from common.configuration import AWSPathManager
from common.protocol import IOTask
from common.resources import Folder, S3Path, File


class RunnableTask(ABC):
    @abstractmethod
    def cmd(self):
        pass

    @abstractmethod
    def cwd(self):
        pass

    @abstractmethod
    def timeout(self):
        pass

    @abstractmethod
    def onBreakDown(self):
        pass

    # stdout reporting
    @abstractmethod
    def onStdout(self, string):
        pass

    # stderr reporting
    @abstractmethod
    def onStderr(self, string):
        pass

    # task timed out reporting
    @abstractmethod
    def onTimeout(self):
        pass

    @abstractmethod
    def onFinished(self, returncode):
        pass


class StdTask(RunnableTask):
    def __init__(self, task: IOTask, serverpath, bucketpath):
        self._taskcfg = task
        self._serverpath = serverpath
        self._bucketpath = bucketpath
        self._lwd = Folder(task.lwd)
        self._output = self._setup_output()
        self._mountdir = self._setup_ws()
        self._logger = logging.getLogger(StdTask.__class__.__name__)

    def _setup_ws(self):
        ws = self._taskcfg.workspace
        mount_dir = self._lwd.join(ws.root)
        mount_dir.create()
        file = S3Path(self._lwd.join(File(ws.local_input)).path, ws.input.key)
        downloader = Download(self._serverpath, self._bucketpath, file, self._taskcfg.command.timeout)
        return Decompress(mount_dir, downloader.execute()).execute()

    def _setup_output(self):
        ws = self._taskcfg.workspace
        return S3Path(self._lwd.join(File(ws.local_output)).path, ws.output.key)

    def _cleanup(self):
        self._output.remove()
        self._mountdir.remove()

    @staticmethod
    def encode(str):
        data = str.encode('utf-8')
        io_bytes = io.BytesIO(data)
        io_bytes.seek(0)
        return io_bytes

    def write_output(self, file_name, str_data):
        try:
            with tarfile.open(self._output.path, "w") as tarball:
                io_bytes = StdTask.encode(str_data)
                tf_info = tarfile.TarInfo(file_name)
                tf_info.size = len(str_data)
                tarball.addfile(tarinfo=tf_info, fileobj=io_bytes)
                tarball.close()
        except Exception as e:
            self._logger.exception("exception %s", e)
            raise TerminateTask()

    def cmd(self):
        cmdcfg = self._taskcfg.command
        if self._taskcfg.perf_file:
            cmd = cmdcfg.shell + ["-o", self._taskcfg.perf_file]
        else:
            cmd = cmdcfg.shell

        if cmdcfg.cores == 1:
            cmd = ["taskset", "-c", "0", "/bin/bash", "-c"] + [" ".join(cmd)]
        else:
            cmd = ["taskset", "-c", "0-{0}".format(str(cmdcfg.cores - 1)), "/bin/bash", "-c"] + [" ".join(cmd)]

        return cmd

    def onStdout(self, string):
        self.write_output("stdout", string)
        return self._output

    def onStderr(self, string):
        self.write_output("stderr", string)
        return self._output

    def onFinished(self, returncode):
        if self._taskcfg.perf_file and returncode:
            perf_file = self._lwd.join(File(self._taskcfg.perf_file))
            if perf_file.exists():
                with tarfile.open(self._output.path) as tarball:
                    tf_info = tarball.gettarinfo(perf_file.path, arcname=perf_file.username)
                    with open(perf_file.path, "rb") as f:
                        tarball.addfile(tarinfo=tf_info, fileobj=f)
                        f.close()
                    tarball.close()
        return Upload(self._serverpath, self._bucketpath, self._output).execute()

    def onTimeout(self):
        self._cleanup()

    def onBreakDown(self):
        self._cleanup()

    def cwd(self):
        return self._mountdir.path

    def timeout(self):
        return self._taskcfg.command.timeout


# throw this onStderr, onStdout, so that we know to terminate
class TerminateTask(Exception):
    pass


class Runner(ABC):
    @abstractmethod
    def run(self):
        pass


class DecoratorRunner(Runner, ABC):
    _decorated: Runner = None

    def __init__(self, runner: Runner):
        self._decorated = runner

    def run(self):
        return self._decorated.run()


class ProcessRunner(Runner):
    def __init__(self, task: RunnableTask):
        self._task = task
        self._pipe = None

    def _kill(self):
        self._task.onBreakDown()
        os.killpg(self._pipe.pid, signal.SIGKILL)

    def run(self):
        try:
            proc = subprocess.Popen(
                self._task.cmd(),
                stdout=subprocess.PIPE,
                cwd=self._task.cwd(),
                shell=False,
                stderr=subprocess.PIPE,
                start_new_session=True,
                universal_newlines=True
            )
            self._pipe = proc
        except OSError as e:
            # OSErrors are raised if there is an issue calling the subprocess
            stdout = ""
            stderr = "Error calling process: " + str(e)
        else:
            try:
                stdout, stderr = proc.communicate(timeout=self._task.timeout())
                try:
                    self._task.onStdout(stdout)
                except TerminateTask:
                    self._kill()

                try:
                    self._task.onStderr(stderr)
                except TerminateTask:
                    self._kill()

                try:
                    self._task.onFinished(proc.returncode)
                except TerminateTask:
                    self._kill()

            except subprocess.TimeoutExpired:
                stdout = ""
                stderr = "Process timed out after {timeout} seconds".format(timeout=self._task.timeout())
                self._task.onTimeout()
            finally:
                try:
                    self._kill()
                except ProcessLookupError:
                    pass


class IOTaskRunner(Runner):
    def __init__(self, json_file, config: AWSPathManager):
        self._task_file = json_file
        self._config = config

    def _setup(self):
        with open(self._task_file, 'r') as reader:
            iotask: IOTask = objectfactory.Factory.create_object(json.loads(reader.read()))
        return iotask

    def run(self):
        try:
            taskdata = self._setup()
            runner = ProcessRunner(StdTask(taskdata, self._config.server_path, self._config.bucket_path))
            runner.run()
        except Exception as e:
            print(e)
            pass
