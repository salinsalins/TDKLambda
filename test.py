class RequiredString:
    def __init__(self):
        print('RequiredString __init__', self)

    def __set_name__(self, owner, name):
        print(f'__set_name__ was called with owner={owner} and name={name}')
        self.property_name = name

    def __get__(self, instance, owner):
        print(f'__get__ was called with instance={instance} and owner={owner}')
        if instance is None:
            return self
        return instance.__dict__[self.property_name] or None

    def __set__(self, instance, value):
        print(f'__set__ was called with instance={instance} and value={value}')
        if not isinstance(value, str):
            raise ValueError(f'The {self.property_name} must a string')
        if len(value) == 0:
            raise ValueError(f'The {self.property_name} cannot be empty')
        instance.__dict__[self.property_name] = value


class Person:
    first_name = RequiredString()
    last_name = RequiredString()

    def __init__(self):
        print('Person __init__', self)

    def __getattribute__(self, item):
        print('__getattribute__', self, item)
        if item == '__dict__':
            return super().__getattribute__(item)
        if hasattr(self, item):
            v = self.__dict__[item]
            if hasattr(v, '__get__'):
                return v.__get__(self)
        return super().__getattribute__(item)

print("*** start")

person = Person()
print("*** after person = Person()", person)

person.first_name = 'John'
print("*** after person.first_name = 'John'", person)
person.last_name = 'Doe'
print("*** after person.last_name = 'Doe'", person)

person.a = RequiredString()
print('---------------', person.a)

person.first_name = 'John'

print(person.__dict__) # {'first_name': 'John', 'last_name': 'Doe'}

print(person.first_name)
print(Person.first_name)
