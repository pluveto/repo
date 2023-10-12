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
