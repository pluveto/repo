# Source Layout - Code Analyzer

A tool to check your Python code layout (order of private/public class member etc).

## Installation

Simply clone or download the repository and place the script in your desired location.

## Usage

The tool is built as a command line application. You can run it providing a single Python file or a path directory contains python files. Utilize the `-v` or `--verbose` option for verbose outputs:

```shell
python source_layout.py
# or
python src/
```

## Example

Input:

```python
class Dog:
    @staticmethod
    def from_dict(d: dict):
        return Dog(d["name"], d["age"])

    name: str

    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age

    def bark(self):
        print(f"{self.name} barks!")

    def __repr__(self):
        return f"Dog(name={self.name}, age={self.age})"

    age: int
```

Output:

```shell
Found issues in examples/example.py:
    examples/example.py:6 "name" should not be after "from_dict"
    examples/example.py:15 "__repr__" should not be after "bark"
    examples/example.py:18 "age" should not be after "__repr__"
```

## Functionality

Here's an brief of what the tool does:

- Parse your Python code
- Enumerate through the objects and nodes of the file(s), and classify them by type (class declarations, class variables, import statements, magic methods, getters&setters, static methods, public/private methods).
- Build a declaration tree resultant from analysis, and check their order.
- The tool can recognize if an object (like a method) is improperly placed in relation to other objects.
- Output a detailed log of the analysis, that can be toggled quiet or verbose.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Any bugs or feature recommendations can be forwarded to the repository's issue tracker.
