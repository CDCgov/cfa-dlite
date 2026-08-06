import re
from pathlib import Path

PYTHON_FENCE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


def test_readme_python_examples_run_without_error():
    readme = Path(__file__).parents[1] / "README.md"
    examples = PYTHON_FENCE.findall(readme.read_text())

    assert examples, "README.md does not contain any Python examples"

    namespace = {"__name__": "__main__"}
    for number, example in enumerate(examples, start=1):
        exec(
            compile(example, f"{readme.name} Python example {number}", "exec"),
            namespace,
        )
