# Copyright (C) 2016  name of Zsolt Szabo zsoltman@hotmail.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
'''Request and response shapes for the JSON API.

These replace the WTForms field generation: forms.py builds its 35 ledger
cells and 12 percentage fields by exec()ing generated source, which cannot
be type-checked or introspected. Here the same inputs are a list of typed
cells and two fixed-length arrays.

Field constraints mirror the WTForms validators exactly, because the
services behind them still assume those bounds:
  * a ledger cell is -1000..1000 (per cell, not per transaction)
  * an allowance amount is 0.01..500
  * a payout day is 1..28, so every month has one
  * a percentage is 0..100, and the axis must total exactly 100
'''
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.domain import buckets

AccountSlot = Annotated[int, Field(ge=1, le=len(buckets.ACCOUNT_SLOTS))]
LocationSlot = Annotated[int, Field(ge=1, le=len(buckets.LOCATION_SLOTS))]
Percent = Annotated[float, Field(ge=0, le=100)]
CellAmount = Annotated[float, Field(ge=-1000, le=1000)]
PayoutDay = Annotated[int, Field(ge=1, le=28)]

ACCOUNT_COUNT = len(buckets.ACCOUNT_SLOTS)
LOCATION_COUNT = len(buckets.LOCATION_SLOTS)


# --- shared ---------------------------------------------------------------

class ErrorBody(BaseModel):
    code: str
    message: str
    fieldErrors: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


class Bucket(BaseModel):
    '''A sub-account or money location.

    `index` is 1-based and is the bucket's identity, not merely its
    position -- see app/api/serializers.py.
    '''
    index: int
    name: Optional[str] = None
    active: bool
    comment: Optional[str] = None


# --- auth -----------------------------------------------------------------

class ActorOut(BaseModel):
    kind: Literal['parent', 'child']
    id: int
    firstname: Optional[str] = None
    moneySymbol: Optional[str] = None


class SessionOut(BaseModel):
    authenticated: bool
    actor: Optional[ActorOut] = None


class ParentLoginIn(BaseModel):
    email: str
    password: str


class ChildLoginIn(BaseModel):
    '''A child's credential is a nickname plus two animals, then a
    password plus two more.'''
    firstname: str
    animal1: str
    animal2: str
    password: str
    animal3: str
    animal4: str


class CsrfOut(BaseModel):
    token: str


class OkOut(BaseModel):
    ok: bool = True


# --- dashboard ------------------------------------------------------------

class KidSummary(BaseModel):
    id: int
    firstname: str
    loginAnimals: List[str]
    balance: float


class DashboardOut(BaseModel):
    actor: ActorOut
    kids: List[KidSummary]
    totalOwed: float
    monthlyOutlay: float
    moneySymbol: str


# --- kids -----------------------------------------------------------------

class KidOut(BaseModel):
    id: int
    firstname: str
    loginAnimals: List[str]
    passwordAnimals: List[str]
    accounts: List[Bucket]
    locations: List[Bucket]
    password: Optional[str] = None


class KidListOut(BaseModel):
    kids: List[KidSummary]


class AnimalOut(BaseModel):
    key: str
    imageUrl: str


class AnimalListOut(BaseModel):
    animals: List[AnimalOut]


class AnimalPairsOut(BaseModel):
    firstname: str
    availablePairs: List[List[str]]


# --- allowances -----------------------------------------------------------

class AllowanceOut(BaseModel):
    id: int
    kidId: int
    nickname: Optional[str] = None
    amount: float
    createdAt: Optional[str] = None
    payoutDays: List[int]
    accountPercents: List[float]
    locationPercents: List[float]


class AllowanceListOut(BaseModel):
    allowances: List[AllowanceOut]


class AllowanceCreateIn(BaseModel):
    amount: Annotated[float, Field(ge=0.01, le=500)]
    nickname: str = 'Allowance'
    payoutDays: Annotated[List[PayoutDay], Field(min_length=1)]
    accountPercents: Annotated[List[Percent],
                               Field(min_length=ACCOUNT_COUNT,
                                     max_length=ACCOUNT_COUNT)]
    locationPercents: Annotated[List[Percent],
                                Field(min_length=LOCATION_COUNT,
                                      max_length=LOCATION_COUNT)]

    @model_validator(mode='after')
    def _splits_total_one_hundred(self):
        '''Both axes must total exactly 100.

        Enforced here for a clear field-level error, and again in the
        service, and a third time by the acc_100/loc_100 CheckConstraints
        in SQLite. The database comparison is on floats, so "close to 100"
        really is rejected.
        '''
        if round(sum(self.accountPercents), 6) != 100:
            raise ValueError(
                'Allowance distribution among sub-accounts must add up '
                'to 100%')
        if round(sum(self.locationPercents), 6) != 100:
            raise ValueError(
                'Allowance storage (where) must add up to 100%')
        return self


# --- ledger ---------------------------------------------------------------

class LedgerCellIn(BaseModel):
    '''One cell of the 5x7 grid: an amount against an (account, location).'''
    account: AccountSlot
    location: LocationSlot
    amount: CellAmount


class LedgerEntryIn(BaseModel):
    cells: Annotated[List[LedgerCellIn], Field(min_length=1)]
    comment: Optional[str] = None
    noComment: bool = False

    @model_validator(mode='after')
    def _comment_or_explicit_opt_out(self):
        if not (self.comment or '').strip() and not self.noComment:
            raise ValueError(
                "You need to select 'no comment' if you want to commit "
                'without a comment')
        return self

    @model_validator(mode='after')
    def _no_duplicate_cells(self):
        '''Two entries for the same cell would silently take the last one.'''
        seen = {(c.account, c.location) for c in self.cells}
        if len(seen) != len(self.cells):
            raise ValueError('Each (account, location) cell may appear once')
        return self


class LedgerEntryOut(BaseModel):
    id: int
    kidId: int
    timestamp: Optional[str] = None
    adjusterName: str
    adjustedByParent: bool
    comment: Optional[str] = None
    accountTotals: List[float]
    locationTotals: List[float]
    accountChanges: List[float]
    locationChanges: List[float]


class LedgerOut(BaseModel):
    kid: KidOut
    entries: List[LedgerEntryOut]
    grandTotal: float
    moneySymbol: str
    visibleAccounts: List[int]
    visibleLocations: List[int]
