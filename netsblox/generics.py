from typing import Any, Union, Optional, Sequence, List, Dict

from PIL import Image
from netsblox import sound as Sound

class AssetSet:
    def __init__(self, *, kind: type = object):
        self.__kind = kind
        self.__ordered: List[str] = []
        self.__unordered: Dict[str, Any] = {}

    def clear(self) -> None:
        '''
        Removes any defined assets, effectively starting from scratch.
        '''
        self.__ordered.clear()
        self.__unordered.clear()

    def add(self, name: str, value: Any) -> None:
        '''
        Adds a single new asset to the collection of assets.
        `name` is the name of the asset and `value` is the actual asset that should be used.
        '''
        if not isinstance(name, str):
            raise RuntimeError(f'asset name must be a string, got {type(name)}')
        if not isinstance(value, self.__kind):
            raise RuntimeError(f'asset value must be {self.__kind}, got {type(value)}')
        if name in self.__unordered:
            raise RuntimeError(f'an asset with name \'{name}\' already exists')

        self.__unordered[name] = value
        self.__ordered.append(name)

    def lookup(self, value: Union[int, str, Any, None]) -> Optional[Any]:
        '''
        Attempts to look up an asset from the collection of assets.
        The value can be specified as any of the following:

         - The name of a previously-added asset (or empty string for no asset)
         - The index of a previously-added asset
         - An asset, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no asset
        '''

        if value is None:
            return None

        if isinstance(value, int):
            return self.__unordered[self.__ordered[value]]

        if isinstance(value, str):
            if value == '':
                return None
            if value in self.__unordered:
                return self.__unordered[value]
            raise RuntimeError(f'unknown asset \'{value}\'')

        if isinstance(value, self.__kind):
            return value

        raise RuntimeError(f'assets must be either a string, int, or asset object - instead got \'{type(value)}\'')

    def index(self, value: Union[int, str, Any, None], default: Optional[int] = None) -> Optional[int]:
        '''
        Attempts to get the index of the provided asset (after lookup).
        If the asset is not found, the default value is returned (or None if not specified).
        '''
        value = self.lookup(value)
        for i, v in enumerate(self.__ordered):
            if self.__unordered[v] is value:
                return i
        return default

    def __len__(self) -> int:
        return len(self.__ordered)

    def __iter__(self) -> Sequence[Any]:
        return (self.__unordered[x] for x in self.__ordered)

class CostumeSet(AssetSet):
    def __init__(self):
        super().__init__(kind = Image.Image)
    def lookup(self, value: Union[int, str, Image.Image, None]) -> Optional[Image.Image]:
        '''
        Attempts to look up an asset from the collection of assets.
        The value can be specified as any of the following:

         - The name of a previously-added asset (or empty string for no asset)
         - The index of a previously-added asset
         - An asset, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no asset
        '''
        return super().lookup(value)

class SoundSet(AssetSet):
    def __init__(self):
        super().__init__(kind = Sound.Sound)
    def lookup(self, value: Union[int, str, Sound.Sound, None]) -> Optional[Sound.Sound]:
        '''
        Attempts to look up an asset from the collection of assets.
        The value can be specified as any of the following:

         - The name of a previously-added asset (or empty string for no asset)
         - The index of a previously-added asset
         - An asset, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no asset
        '''
        return super().lookup(value)
