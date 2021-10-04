from __future__ import annotations

import shutil
from abc import ABC
import json
import os
import urllib.request
from urllib.parse import urlparse
from multipledispatch import dispatch


class Path(object):
    path = property(fget=lambda self: self._identity())

    def __init__(self, id):
        self._id = id

    def _identity(self):
        return self._id


class OSPath(Path, ABC):
    parent = property(fget=lambda self: self._parent())
    name = property(fget=lambda self: self._name(), fset=lambda self, v: self._rename(v))

    def __init__(self, ospath: str):
        super().__init__(ospath)
        self._init, self._last = os.path.split(ospath)

    def _parent(self):
        return self._init

    def _name(self):
        return self._last

    def _rename(self, name):
        self._last = name

    def exists(self):
        return os.path.exists(self.path)

    @staticmethod
    def new(ospath: str):
        if os.path.isfile(ospath):
            return File(ospath)
        elif os.path.isdir(ospath):
            return Folder(ospath)
        else:
            # not in system yet
            if not ospath.endswith(os.path.sep):
                return File(ospath)
            else:
                return Folder(ospath)


class File(OSPath):
    def __init__(self, id: str):
        assert not id.endswith(os.path.sep)
        super().__init__(id)

    @property
    def extension(self):
        name, ext = os.path.splitext(self.name)
        return ext

    def remove(self):
        os.remove(self.path)

    def content(self, header=" START ", footer=" END "):
        print(" ====  {0}  ====\n".format(header))
        with open(self.path, 'r') as f:
            print(f.read())
        print(" ====  {0}  ====\n".format(footer))


class Folder(OSPath):
    def __init__(self, id: str):
        super().__init__(os.path.normpath(id))

    def create(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        return self

    def _identity(self):
        return self._id + os.path.sep

    # figures out the relative path of this against path p.
    def relative(self, p: OSPath):
        return Path(os.path.normpath(os.path.relpath(p.path, self.path)))

    @dispatch(File)
    def join(self, p: File):
        return File(os.path.join(self.path, p.path))

    @dispatch(OSPath)
    def join(self, p: Folder):
        return Folder(os.path.join(self.path, p.path))

    def remove(self):
        shutil.rmtree(self.path)

    @staticmethod
    def cwd():
        return Folder(os.path.normpath(os.getcwd()))


class S3Path(OSPath):
    def __init__(self, id: str, key: str):
        self._decorated = OSPath.new(id)
        self._key = key

    def _parent(self):
        return self._decorated._parent()

    def _name(self):
        return self._decorated._name()

    def _rename(self, name):
        self._decorated._rename(name)

    def _identity(self):
        return self._decorated._identity()

    @property
    def key(self):
        return self._key

    @property
    def ospath(self):
        return self._decorated

    def remove(self):
        os.remove(self.path)


class URL(Path):
    def __init__(self, url: str):
        super().__init__(url)

    def isvalid(self):
        try:
            result = urlparse(self.path)
            return all([result.scheme, result.netloc])
        except:
            return False

    def read(self):
        print(self.path)
        with urllib.request.urlopen(self.path) as url:
            decoded = url.read().decode()
            return json.loads(decoded)

    def save(self, ofname):
        content = self.read()
        with open(ofname) as outfile:
            json.dump(content, ofname)
        return content


class JsonLoader:
    @staticmethod
    def load_url(urlstr:str):
        url = URL(urlstr)
        if url.isvalid():
            data = url.read()
            return data
        else:
            raise RuntimeError("url is invalid")

    @staticmethod
    def load_file(file:str):
        if os.path.exists(file):
            with open(file) as cfg:
                data = json.load(cfg)
            return data
        else:
            raise RuntimeError("configuration not found!!!")