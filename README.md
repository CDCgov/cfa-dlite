# fiat

Minimal workflow orchestration.

"Fiat" is Latin, the third person singular passive present subjunctive of *facio*; that is, "let it be done."

## Overview

### Assets

fiat allows you to create a *catalog* of *assets*, each with an associated *function* and *store*.
We *get* the value of an asset by reading from the asset's store or from the asset's function.

The simplest store is an in-memory cache:

```python
from fiat import Asset, Catalog, MemoryStore


def my_expensive_function():
    print("this is slow!")
    return "return value"


catalog = Catalog(
    Asset(id="expensive!", fun=my_expensive_function, store=MemoryStore())
)

print(catalog.get("expensive!"))
print(catalog.get("expensive!"))
# > this is slow!
# > return value
# > return value
```

Asset IDs can be any value and default to the function name.
An asset defined by `Asset(fun=my_function, store=...)` would be accessed with `catalog.get(my_function)`.

fiat has a convenience wrapper around functions:

```python
from fiat import Asset, Catalog, MemoryStore

catalog = Catalog()


# this is the wrapper way
@catalog.as_asset(store=MemoryStore())
def f():
    return "return value"


assert f() == "return value"


# that's equivalent to:
# - making a new "inner" function that does the work
# - making an "outer" function, which has the name of the original function, but
#   which actually queries the catalog for the "inner" value
# - adding the "inner" function as an asset
def g_inner():
    return "return value"


def g():
    return catalog.get(g_inner)


catalog.add(Asset(fun=g_inner, store=MemoryStore()))
assert g() == "return value"
```

### Stores

Use file stores like `PickleStore` and `ParquetStore` to create persistent artifacts:

```python
from fiat import Catalog, ParquetStore, PickleStore
import tempfile
import polars as pl
from pathlib import Path

# create a store from the directory name
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    catalog = Catalog()

    @catalog.as_asset(PickleStore(td / "my_object.pkl"))
    def my_object():
        return None

    @catalog.as_asset(ParquetStore(td / "my_dataframe.parquet"))
    def my_dataframe() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    print(my_object())
    print(my_dataframe())
    # my_object.pkl and my_dataframe.parquet will appear in the td
```

### Dependencies

*In progress*: fiat implements a greedy DAG: if one asset depends on another, it will cause those other assets to be materialized first:

```python
from fiat import Catalog, MemoryStore

catalog = Catalog()


@catalog.as_asset(MemoryStore())
def one():
    return 1


@catalog.as_asset(MemoryStore())
def two():
    return 2


@catalog.as_asset(MemoryStore())
def three():
    return one() + two()
```

## Design principles

- Don't require the workflow to be organized differently.
  You can treat the assets as first-class objects, and use `catalog.get`.
  Or, you can use `@catalog.as_asset` and keep the rest of the code the same.
- The catalog creates a namespace orthogonal to the canonical namespace.
  This enables the prior principle.
- Every asset has a different store.
  This way an upstream data source might be in the cloud, but downstream ones might be on disk.

## Future directions

- Create a "freshness" concept.
  Have different ways to express "freshness":
    1. "It's fresh if it exists": This is the simplest, what I've done so far.
    1. "It's fresh if it's newer than its dependencies": This is the `make` concept.
    1. "It's fresh if <some logic>": This is where I want to go.
       E.g., maybe I want new case data every day, but then all downstream files are `make`-type freshness.
- Implement dependencies and the DAG
- Cloud storage protocols
- How to deal with wildcards

## Admins

- Scott Olesen (CDC/CFA) <ulp7@cdc.gov>

## Disclaimers

### General Disclaimer

This repository was created for use by CDC programs to collaborate on public health related projects in support of the [CDC mission](https://www.cdc.gov/about/cdc/index.html).
GitHub is not hosted by the CDC, but is a third party website used by CDC and its partners to share information and collaborate on software.
CDC use of GitHub does not imply an endorsement of any one particular service, product, or enterprise.

### Public Domain Standard Notice

This repository constitutes a work of the United States Government and is not subject to domestic copyright protection under 17 USC § 105.
This repository is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
All contributions to this repository will be released under the CC0 dedication.
By submitting a pull request you are agreeing to comply with this waiver of copyright interest.

### License Standard Notice

This repository is licensed under Apache-2.0 or later.

This source code in this repository is free: you can redistribute it and/or modify it under the terms of the Apache License, Version 2.0, or (at your option) any later version.

This source code in this repository is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the Apache Software License for more details.

You should have received a copy of the Apache Software License along with this program.
If not, see http://www.apache.org/licenses/LICENSE-2.0.html

The source code forked from other open source projects will inherit its license.

### Privacy Standard Notice

This repository contains only non-sensitive, publicly available data and information.
All material and community participation is covered by the [Disclaimer](https://github.com/CDCgov/template/blob/master/DISCLAIMER.md) and [Code of Conduct](https://github.com/CDCgov/template/blob/master/code-of-conduct.md).
For more information about CDC's privacy policy, please visit [http://www.cdc.gov/other/privacy.html](https://www.cdc.gov/other/privacy.html).

### Contributing Standard Notice

Anyone is encouraged to contribute to the repository by [forking](https://help.github.com/articles/fork-a-repo) and submitting a pull request.
(If you are new to GitHub, you might start with a [basic tutorial](https://help.github.com/articles/set-up-git).)
By contributing to this project, you grant a world-wide, royalty-free, perpetual, irrevocable, non-exclusive, transferable license to all users under the terms of the [Apache Software License v2](http://www.apache.org/licenses/LICENSE-2.0.html) or later.

All comments, messages, pull requests, and other submissions received through CDC including this GitHub page may be subject to applicable federal law, including but not limited to the Federal Records Act, and may be archived.
Learn more at <http://www.cdc.gov/other/privacy.html>.

### Records Management Standard Notice

This repository is not a source of government records but is a copy to increase collaboration and collaborative potential.
All government records will be published through the [CDC web site](http://www.cdc.gov).
