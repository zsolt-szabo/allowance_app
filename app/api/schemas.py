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


class CaptchaOut(BaseModel):
    """A registration captcha.

    The digits are served as image URLs, not as text, which is the whole
    point of it. The expected answer stays server-side in the session.
    """
    operation: str
    firstDigits: List[str]
    secondDigits: List[str]


class ParentCreateIn(BaseModel):
    email: str
    firstname: str
    password: str
    moneySymbol: Annotated[str, Field(min_length=1, max_length=2)] = '$'
    captcha: str


class ParentOut(BaseModel):
    id: int
    email: str
    firstname: Optional[str] = None
    moneySymbol: str
    isGoogle: bool


class ParentUpdateIn(BaseModel):
    firstname: Optional[str] = None
    moneySymbol: Optional[Annotated[str,
                                    Field(min_length=1, max_length=2)]] = None
    oldPassword: Optional[str] = None
    newPassword: Optional[str] = None


class ConfirmIn(BaseModel):
    """Destructive operations require saying so explicitly."""
    confirm: bool = False


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


class BucketIn(BaseModel):
    index: int = Field(ge=1, le=LOCATION_COUNT)
    name: Optional[str] = None
    active: bool = False
    comment: Optional[str] = None


class KidCreateIn(BaseModel):
    firstname: Annotated[str, Field(min_length=1, max_length=80)]
    password: Annotated[str, Field(min_length=2, max_length=80)]
    loginAnimals: Annotated[List[str], Field(min_length=2, max_length=2)]
    passwordAnimals: Annotated[List[str], Field(min_length=2, max_length=2)]
    accounts: Annotated[List[BucketIn], Field(min_length=ACCOUNT_COUNT,
                                              max_length=ACCOUNT_COUNT)]
    locations: Annotated[List[BucketIn], Field(min_length=LOCATION_COUNT,
                                               max_length=LOCATION_COUNT)]

    @model_validator(mode='after')
    def _at_least_one_of_each(self):
        """Mirrors the at_least_one_acc / at_least_one_location
        CheckConstraints, which would otherwise reject the INSERT."""
        if not any(b.active for b in self.accounts):
            raise ValueError('At least one sub-account must be active')
        if not any(b.active for b in self.locations):
            raise ValueError('At least one money location must be active')
        return self

    @model_validator(mode='after')
    def _named_when_active(self):
        for bucket in list(self.accounts) + list(self.locations):
            if bucket.active and not (bucket.name or '').strip():
                raise ValueError('An active bucket needs a name')
        return self


class KidUpdateIn(BaseModel):
    """Every field optional: this is a partial update."""
    firstname: Optional[Annotated[str, Field(min_length=1,
                                             max_length=80)]] = None
    password: Optional[Annotated[str, Field(min_length=2,
                                            max_length=80)]] = None
    loginAnimals: Optional[Annotated[List[str],
                                     Field(min_length=2,
                                           max_length=2)]] = None
    passwordAnimals: Optional[Annotated[List[str],
                                        Field(min_length=2,
                                              max_length=2)]] = None
    accounts: Optional[Annotated[List[BucketIn],
                                 Field(min_length=ACCOUNT_COUNT,
                                       max_length=ACCOUNT_COUNT)]] = None
    locations: Optional[Annotated[List[BucketIn],
                                  Field(min_length=LOCATION_COUNT,
                                        max_length=LOCATION_COUNT)]] = None


class KidUpdateOut(BaseModel):
    kid: KidOut
    #  Allowances whose distribution could not be repaired after a bucket
    #  was switched off; the parent has to recreate these.
    orphanedAllowances: List[str] = []


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
