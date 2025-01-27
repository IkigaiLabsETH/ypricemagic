
import asyncio
from contextlib import suppress
from functools import cached_property
from typing import Any, Optional, Tuple, Union

import a_sync
from brownie.convert.datatypes import HexString
from brownie.exceptions import ContractNotFound

from y import convert
from y.classes.singleton import ChecksumASyncSingletonMeta
from y.constants import EEE_ADDRESS
from y.contracts import Contract, build_name, has_method, probe
from y.datatypes import AnyAddressType, Block, Pool, UsdPrice
from y.erc20 import decimals, totalSupply
from y.exceptions import (ContractNotVerified, MessedUpBrownieContract,
                          NonStandardERC20)
from y.networks import Network
from y.utils import logging, raw_calls


def hex_to_string(h: HexString) -> str:
    '''returns a string from a HexString'''
    h = h.hex().rstrip("0")
    if len(h) % 2 != 0:
        h += "0"
    return bytes.fromhex(h).decode("utf-8")

class ContractBase(a_sync.ASyncGenericBase, metaclass=ChecksumASyncSingletonMeta):
    def __init__(self, address: AnyAddressType, asynchronous: bool = False) -> None:
        self.address = convert.to_address(address)
        self.asynchronous = asynchronous
        super().__init__()
    
    def __str__(self) -> str:
        return f'{self.address}'

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.address}'"
    
    def __eq__(self, __o: object) -> bool:
        try:
            return convert.to_address(__o) == self.address
        except Exception:
            return False
    
    def __hash__(self) -> int:
        return hash(self.address)
    
    @property
    def contract(self) -> Contract:
        return Contract(self.address)
    
    @cached_property
    def _is_cached(self) -> bool:
        try:
            self.contract
            return True
        except (ContractNotVerified):
            return False
        except (ContractNotFound, MessedUpBrownieContract):
            return None

    @a_sync.aka.cached_property
    async def build_name(self) -> str:
        return await build_name(self.address, sync=False)

    async def has_method(self, method: str, return_response: bool = False) -> Union[bool,Any]:
        return await has_method(self.address, method, return_response=return_response, sync=False)


class ERC20(ContractBase):
    def __repr__(self) -> str:
        cls = self.__class__.__name__
        with suppress(AttributeError):
            if ERC20.symbol.has_cache_value(self):
                symbol = ERC20.symbol.get_cache_value(self)
                return f"<{cls} {symbol} '{self.address}'>"
            elif not asyncio.get_event_loop().is_running() and not self.asynchronous:
                return f"<{cls} {self.symbol} '{self.address}'>"
        return super().__repr__()
    
    @a_sync.aka.cached_property
    async def symbol(self) -> str:
        if self.address == EEE_ADDRESS:
            return "ETH"
        
        symbol = await probe(self.address, ["symbol()(string)", "SYMBOL()(string)", "getSymbol()(string)"])
        if symbol:
            return symbol
        
        # Sometimes the above will fail if the symbol method returns bytes32, as with MKR. Let's try this.
        symbol = await probe(self.address, ["symbol()(bytes32)"])
        if symbol:
            return hex_to_string(symbol)

        # we've failed to fetch
        self.__raise_exception('symbol')
    
    @a_sync.aka.cached_property
    async def name(self) -> str:
        if self.address == EEE_ADDRESS:
            return "Ethereum"
        
        name = await probe(self.address, ["name()(string)", "NAME()(string)", "getName()(string)"])
        if name:
            return name
        
        # Sometimes the above will fail if the name method returns bytes32, as with MKR. Let's try this.
        name = await probe(self.address, ["name()(bytes32)"])
        if name:
            return hex_to_string(name)
                
        # we've failed to fetch
        self.__raise_exception('name')
    
    @a_sync.aka.cached_property
    async def decimals(self) -> int:
        if self.address == EEE_ADDRESS:
            return 18
        return await decimals(self.address, sync=False)

    @a_sync.a_sync # Override the leading underscore so a_sync lib doesn't bypass this fn
    async def _decimals(self, block: Optional[Block] = None) -> int:
        '''used to fetch decimals at specific block'''
        if self.address == EEE_ADDRESS:
            return 18
        retval = await decimals(self.address, block=block, sync=False)
        if asyncio.iscoroutine(retval):
            raise Exception(retval)
        return retval
    
    @a_sync.aka.cached_property
    async def scale(self) -> int:
        return 10 ** await self.__decimals__(asynchronous=True)
    
    @a_sync.a_sync # Override the leading underscore so a_sync lib doesn't bypass this fn
    async def _scale(self, block: Optional[Block] = None) -> int:
        return 10 ** await self._decimals(block, sync=False)

    async def total_supply(self, block: Optional[Block] = None) -> int:
        return await totalSupply(self.address, block=block, sync=False)

    async def total_supply_readable(self, block: Optional[Block] = None) -> float:
        total_supply, scale = await asyncio.gather(
            self.total_supply(block=block, sync=False),
            self.__scale__(sync=False)
        )
        return total_supply / scale
    
    async def balance_of(self, address: AnyAddressType, block: Optional[Block] = None) -> int:
        return await raw_calls.balanceOf(self.address, address, block=block, sync=False)
    
    async def balance_of_readable(self, address: AnyAddressType, block: Optional[Block] = None) -> float:
        balance, scale = await asyncio.gather(self.balance_of(address, block=block, asynchronous=True), self.__scale__(asynchronous=True))
        return balance / scale

    async def price(
        self, 
        block: Optional[Block] = None, 
        return_None_on_failure: bool = False, 
        ignore_pools: Tuple[Pool, ...] = (),
    ) -> Optional[UsdPrice]:
        from y.prices.magic import get_price
        return await get_price(
            self.address, 
            block=block, 
            fail_to_None=return_None_on_failure,
            ignore_pools=ignore_pools,
            sync=False,
        )
    
    def __raise_exception(self, fn_name: str):
        raise NonStandardERC20(f'''
            Unable to fetch `{fn_name}` for {self.address} on {Network.printable()}
            If the contract is verified, please check to see if it has a strangely named
            `{fn_name}` method and create an issue on https://github.com/BobTheBuidler/ypricemagic
            with the contract address and correct method name so we can keep things going smoothly :)''')


class WeiBalance(a_sync.ASyncGenericBase):
    def __init__(
        self, 
        balance: int,
        token: AnyAddressType,
        block: Optional[Block] = None,
        ignore_pools: Tuple[Pool, ...] = (),
        asynchronous: bool = False,
        ) -> None:

        self.asynchronous = asynchronous
        self.balance = balance
        self.token = ERC20(str(token), asynchronous=self.asynchronous)
        self.block = block
        super().__init__()
        self._logger = logging.get_price_logger(token, block, self.__class__.__name__)
        self._ignore_pools = ignore_pools

    def __str__(self) -> str:
        return str(self.balance)
    
    def __repr__(self) -> str:
        return f"<WeiBalance token={self.token} balance={self.balance} block={self.block}>"

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, int):
            return __o == self.balance
        elif isinstance(__o, WeiBalance):
            return self.balance == __o.balance and self.token == __o.token
        return False
    
    def __lt__(self, __o: object) -> bool:
        if isinstance(__o, int):
            return __o < self.balance
        elif isinstance(__o, WeiBalance):
            if self.token != __o.token:
                raise TypeError(f"'<' only supported between {self.__class__.__name__} instances when denominated in the same token.")
            return self.balance < __o.balance
        raise TypeError(f"'<' not supported between instances of '{self.__class__.__name__}' and '{__o.__class__.__name__}'")

    def __ge__(self, __o: object) -> bool:
        if __o < self:
            return True
        elif type(__o) is type(self):
            return self == __o
        raise TypeError(f"'>=' not supported between instances of '{self.__class__.__name__}' and '{__o.__class__.__name__}'")
    
    @a_sync.aka.property
    async def readable(self) -> float:
        if self.balance == 0:
            return 0
        scale = await self.token.__scale__(sync=False)
        readable = self.balance / scale
        self._logger.debug("balance: %s  decimals: %s  readable: %s", self.balance, str(scale).count("0"), readable)
        return readable
    
    @a_sync.aka.cached_property
    async def value_usd(self) -> float:
        if self.balance == 0:
            return 0
        balance, price = await asyncio.gather(
            self.__readable__(sync=False),
            self.token.price(block=self.block, ignore_pools=self._ignore_pools, sync=False),
        )
        value = balance * price
        self._logger.debug("balance: %s  price: %s  value: %s", balance, price, value)
        return value
