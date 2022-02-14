import time
import atexit
import threading
import randomname
from typing import Any, Optional, Dict, MutableSet, Literal, Tuple

LOGGING = False
def log(*args, **kwargs):
    if LOGGING: print(*args, **kwargs)

def format_room_id(room_name: str) -> str:
    return f'_pyblox_room({room_name})'

class RcRoomHandle:
    '''
    A distributed reference-counted handle to pyblox room metadata.

    The first constructed handle for a given room will initialize the room to a valid empty state.
    It is important that this initial (room creation) constructed handle does not pose a race condition.
    After room creation, new handles may be created using the same room id and password,
    and will simply modify the reference counter atomically as needed.
    To ensure proper cleanup, you must call `destroy()` when the handle is no longer being used.
    '''

    def __init__(self, client: Any, room_id: str, password: Optional[str] = None, *, mode: Literal['create', 'join']):
        self.__constructed = False

        self.__client = client
        self.__id = room_id
        self.__password = password

        self.__destroyed = False
        self.__destroyed_lock = threading.Lock()

        if mode == 'create':
            try:
                log('creating room', self.__id, 'pass:', self.__password)
                self.__client.cloud_variables.set_variable(self.__id, [1, {}], self.__password)
            except Exception as e:
                err = str(e).lower()
                log('failed...', err)
                if 'incorrect password' in err: raise RuntimeError(f'Failed to create room: room already exists')
                raise e
        elif mode == 'join':
            try:
                log('incrementing room ref counter')
                self.__client.cloud_variables.lock_variable(self.__id, self.__password)
                raw = self.__client.cloud_variables.get_variable(self.__id, self.__password)
                raw[0] += 1
                self.__client.cloud_variables.set_variable(self.__id, raw, self.__password)
                self.__client.cloud_variables.unlock_variable(self.__id, self.__password)
                log('new counter value', raw[0])
            except Exception as e:
                err = str(e).lower()
                log('failed...', err)
                if 'not found' in err: raise RuntimeError(f'Failed to connect to room: room does not exist')
                if 'incorrect password' in err: raise RuntimeError(f'Failed to connect to room: incorrect password')
                raise e
        else:
            raise RuntimeError(f'Unknown RcRoomHandle mode: \'{mode}\'')

        self.__constructed = True

    def destroy(self) -> None:
        if not self.__constructed: return

        if self.__destroyed: return
        with self.__destroyed_lock:
            if self.__destroyed: return
            self.__destroyed = True

        log('decrementing room ref counter')
        self.__client.cloud_variables.lock_variable(self.__id, self.__password)
        raw = self.__client.cloud_variables.get_variable(self.__id, self.__password)
        raw[0] -= 1
        self.__client.cloud_variables.set_variable(self.__id, raw, self.__password)
        self.__client.cloud_variables.unlock_variable(self.__id, self.__password)
        log('new counter value', raw[0])

        if raw[0] == 0:
            log('deleting room')
            self.__client.cloud_variables.delete_variable(self.__id, self.__password)

        self.__client = None
        self.__id = None
        self.__password = None

    def __del__(self) -> None:
        self.destroy()

    def __impl_read(self) -> Tuple[int, Dict[str, MutableSet[str]]]:
        assert not self.__destroyed
        raw = self.__client.cloud_variables.get_variable(self.__id, self.__password)
        return [raw[0], { k: set(v) for k, v in raw[1] }]

    def read(self) -> Dict[str, MutableSet[str]]:
        return self.__impl_read()[1]

    def __enter__(self) -> Dict[str, MutableSet[str]]:
        self.__client.cloud_variables.lock_variable(self.__id, self.__password)
        self.__cached = self.__impl_read()
        return self.__cached[1]

    def __exit__(self, *args, **kwargs) -> None:
        self.__client.cloud_variables.set_variable(self.__id, self.__cached, self.__password)
        self.__client.cloud_variables.unlock_variable(self.__id, self.__password)
        self.__cached = None

class EditorRoomManager:
    def __init__(self, *, client: Any):
        self.__client = client
        self.__handle = None
        self.__room_name = None
        self.__room_password = None

    def destroy(self) -> None:
        if self.__handle is not None:
            self.__handle.destroy()

        self.__client = None
        self.__handle = None
        self.__room_name = None
        self.__room_password = None

    def __del__(self) -> None:
        self.destroy()

    @property
    def room_name(self) -> Optional[str]:
        return self.__room_name
    @property
    def room_id(self) -> Optional[str]:
        return format_room_id(self.__room_name)
    @property
    def room_password(self) -> Optional[str]:
        return self.__room_password

    def create_room(self, password: Optional[str] = None) -> None:
        room_name = randomname.get_name()
        new_handle = RcRoomHandle(self.__client, format_room_id(room_name), password, mode = 'create')

        if self.__handle is not None:
            self.__handle.destroy()

        self.__handle = new_handle
        self.__room_name = room_name
        self.__room_password = password

    def join_room(self, room_name: str, password: Optional[str] = None) -> None:
        new_handle = RcRoomHandle(self.__client, format_room_id(room_name), password, mode = 'join')

        if self.__handle is not None:
            self.__handle.destroy()

        self.__handle = new_handle
        self.__room_name = room_name
        self.__room_password = password

    def leave_room(self) -> None:
        if self.__handle is not None:
            self.__handle.destroy()

        self.__handle = None
        self.__room_name = None
        self.__room_password = None

class RuntimeRoomManager:
    CACHE_LIFETIME = 2 # seconds - keep low so little delay before new users are recognized

    def __init__(self, *, client: Any, role: str, room_id: str, password: Optional[str] = None):
        self.__role = role
        self.__pub_id = client.public_id
        self.__handle = None
        self.__handle = RcRoomHandle(client, room_id, password, mode = 'join')

        self.__cached_roles_expiry = 0
        self.__cached_roles_lock = threading.Lock()
        self.__cached_roles = None

        with self.__handle as info:
            if role not in info:
                info[role] = set()
            info[role].add(self.__pub_id)

        atexit.register(self.destroy)

    def destroy(self) -> None:
        if self.__handle is not None:
            with self.__handle as info:
                bucket = info[self.__role]
                bucket.remove(self.__pub_id)
                if len(bucket) == 0:
                    del info[self.__role]
            self.__handle.destroy()

        self.__role = None
        self.__pub_id = None
        self.__handle = None

    def __del__(self) -> None:
        self.destroy()

    def get_roles(self) -> Dict[str, MutableSet[str]]:
        now = time.time()
        if now < self.__cached_roles_expiry:
            return self.__cached_roles

        with self.__cached_roles_lock:
            if now < self.__cached_roles_expiry:
                return self.__cached_roles
            self.__cached_roles = self.__handle.read()
            self.__cached_roles_expiry = time.time() + self.CACHE_LIFETIME

        return self.__cached_roles
