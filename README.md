# fiat

Minimal workflow orchestration.

"Fiat" is Latin, the third person singular passive present subjunctive of *facio*; that is, "let it be done."

## Why another workflow orchestrator?

- If your workflow takes more than 5 minutes, use dagster.
- If your workflow takes less than 5 seconds, forget about a DAG or persistence.
  Run the whole thing every time with a task runner.
- If you only need existing CLI commands, use `make`.
- If your workflow takes an intermediate amount of time, and you want persistence, but you don't need sophisticated config management, use fiat.

## Overview

### Assets

fiat allows you to create a *catalog* of *assets*.
We *get* the *value* of an asset.
Assets are either *sources* or *products*.
A source is read-only: its value can only be read from a *store*.
A product is read-write.
If the value is in the store, the value is read.
If not, the value is computed based on the product's *function*, which can take other assets as input.
The value is written into the store.

The simplest store is an in-memory cache:

```python
from fiat import Asset, Catalog, MemoryStore, Product


def f():
    print("this is slow!")
    return 1


catalog = Catalog()
catalog.add_asset(Product(fun=f, store=MemoryStore()))

# on the first call, the value is computed and stored
print(catalog.get("f"))
# -> this is slow!
# -> 1

# on the second call, the value is simple read from the store
print(catalog.get("f"))
# -> 1


# fiat provides a convenience wrapper for products:
@catalog.as_product(MemoryStore())
def g():
    return 2


assert catalog.get("g") == 2
```

### Stores

File stores like `PickleStore` and `ParquetStore` can read and write persistent artifacts:

```python
from fiat import Catalog, ParquetStore, PickleStore
import tempfile
import polars as pl
from pathlib import Path

# create a store from the directory name
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    catalog = Catalog()

    @catalog.as_product(PickleStore(td / "my_object.pkl"))
    def my_object():
        return {"my": "dictionary"}

    @catalog.as_product(ParquetStore(td / "my_dataframe.parquet"))
    def my_dataframe() -> pl.DataFrame:
        return pl.DataFrame({"x": [1, 2, 3]})

    catalog.get("my_object")
    catalog.get("my_dataframe")
    # my_object.pkl and my_dataframe.parquet will appear in the temporary directory
```

`TomlStore` is read-only; it can be used for sources but not products.

### Dependencies

A product function can take other assets as arguments:

```python
from fiat import Catalog, MemoryStore

catalog = Catalog()


@catalog.as_product(MemoryStore())
def one() -> int:
    return 1


@catalog.as_product(MemoryStore())
def two(one) -> int:
    return one + one


assert catalog.get("two") == 2
```

A product cannot take anything other than an asset as an argument.
Therefore, configs must be passed in as sources:

```python
import tempfile
from fiat import Catalog, Source, TomlStore

my_config = """
[parameters]
beta = 0.5
gamma = 2.0
"""

with tempfile.TemporaryDirectory() as td:
    config_path = Path(td) / "config.toml"
    with open(config_path, "w") as f:
        f.write(my_config)

    catalog = Catalog()
    catalog.add_asset(Source(id="config", store=TomlStore(config_path)))

    @catalog.as_product(MemoryStore())
    def r0(config):
        return config["parameters"]["beta"] / config["parameters"]["gamma"]

    assert catalog.get("r0") == 0.25
```

### Freshness

When calling `catalog.get("my_asset")`, the catalog will ensure that the asset is "fresh" before returning its value.

A source is fresh if it is materialized (e.g., a file exists on disk).
A product is fresh if:

1. it is materialized,
1. its *mtime* is later (i.e., it is younger) than any of its *dependencies*, or
1. all its *ancestors* (recursive dependencies of dependencies) are fresh.

Each store is responsible for determining if its assets are materialized and returning their mtimes.

## Design principles

- Borrow dagster concepts.
  The asset is different from its materialization.
  The asset function's signature specifies dependencies.
- Explicit over implicit.
  There is an explicit catalog, rather than global `@dagster.asset` calls.
- Config is an asset.
- The catalog creates a namespace orthogonal to the canonical namespace.
- Every asset has a different store.
  This way an upstream data source might be in the cloud, but downstream ones might be on disk.

## Future directions

- Try this on some repos
- Cloud storage protocols

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
