import functools
import threading

from wrapt import decorator


def reconcile_meta(*classes):
    metaclass = tuple(set(type(cls) for cls in classes))
    metaclass = metaclass[0] if len(metaclass) == 1 \
        else type("_".join(mcls.__name__ for mcls in metaclass), metaclass, {})
    return metaclass("_".join(cls.__name__ for cls in classes), classes, {})


def Singleton(cls):
    cls._state = {}
    orig_init = cls.__init__

    def new_init(self, *args, **kwargs):
        self.__dict__ = cls._state
        orig_init(self, *args, **kwargs)

    cls.__init__ = new_init
    return cls


def thread_run(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import threading
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper


def thread_it(thread_count=1):
    def wrapper(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import threading
            for i in range(thread_count):
                threading.Thread(target=func, args=args, kwargs=kwargs).start()

        return wrapper

    return wrapper


@decorator
def synchronized(wrapped, instance, args, kwargs):
    if instance is None:
        owner = wrapped
    else:
        owner = instance
    lock = vars(owner).get('_synchronized_lock', None)
    if lock is None:
        meta_lock = vars(synchronized).setdefault(
            '_synchronized_meta_lock', threading.Lock())
        with meta_lock:
            lock = vars(owner).get('_synchronized_lock', None)
            if lock is None:
                lock = threading.RLock()
                setattr(owner, '_synchronized_lock', lock)
    with lock:
        return wrapped(*args, **kwargs)
