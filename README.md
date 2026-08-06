# fiat

Minimal workflow orchestration.
So let it be written, so let it be done.

## Overview

fiat allows you to create *assets*, tracked in a *registry*, with associated an associated *storage* protocol.
The simplest storage is in memory, which reimplements a simple cache:

```python
from fiat import AssetRegistry, MemoryStorage, asset

storage = MemoryStorage()
registry = AssetRegistry(storage)


@asset(registry)
def my_expensive_function():
    print("this is slow!")
    return "hard to find"


print(my_expensive_function())
print(my_expensive_function())
# > this is slow!
# > hard to find
# > hard to find
```

fiat implements a greedy DAG: if one asset depends on another, it will cause those others to be instantiated first:

```python
@asset(registry)
def one():
    return 1


@asset(registry)
def two():
    return 2


@asset(registry, deps=["one", "two"])
def three(one, two):
    return one + two
```

You can use `FileStorage` to create persistent artifacts:

```python
storage = FileStorage("/path/to/my/data")
registry = AssetRegistry(storage)

@asset(format="parquet")
def my_raw_data() -> pl.DataFrame:
    # download raw data from the internet

print(my_raw_data())
```

Then `/path/to/my/data/my_raw_data.parquet` will appear!

## Future directions

- Cloud storage protocols
- Think harder about the dependency specification. For purely greedy, "it's fresh if it exists" assets, then you don't even need to specify dependencies. There's probably no need to have the dependencies as arguments.
- Have different ways to express "freshness":
    1. "It's fresh if it exists": This is the simplest, what I've done so far.
    1. "It's fresh if it's newer than its dependencies": This is the `make` concept.
    1. "It's fresh if <some logic>": This is where I want to go. E.g., maybe I want new case data every day, but then all downstream files are `make`-type freshness.

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
