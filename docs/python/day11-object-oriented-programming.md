# Lesson 11 — Object-Oriented Programming

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day10 — Type Hints

Next Lesson: Day12 — Context Managers

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain OOP as a way to manage complex systems, not just write classes.
* Explain object, class, instance, state, behavior, and `self`.
* Explain class attributes, instance attributes, and shadowing.
* Explain attribute lookup and method lookup.
* Explain inheritance, method override, `super()`, and basic MRO.
* Explain why modern backend systems often prefer composition over inheritance.
* Connect OOP to FastAPI, Playwright, and AI backend architecture.
* Identify common OOP production bugs.
* Answer beginner, intermediate, and senior OOP interview questions.

---

# Why This Matters

Object-Oriented Programming is not about writing `class` because it looks professional.

OOP exists because production systems have many moving parts.

Tech Lead Question:

When a backend grows, what becomes harder first: writing syntax, or managing
responsibility?

Think first.

Student Answer:

"Managing responsibility. We need to know which part owns which data and behavior."

Tech Lead Explanation:

Exactly.

OOP is a responsibility-management tool.

It helps answer:

```text
Who owns this state?
Who owns this behavior?
Can this object be reused safely?
Is this relationship Is-A or Has-A?
Should this be inheritance or composition?
```

Day01 taught:

```text
Everything
      |
      v
    Object
```

Day11 returns to that idea at engineering scale.

Python's unified object model reduces language complexity because functions, classes,
modules, exceptions, and instances all behave as objects with identity, attributes, and
behavior.

In FastAPI, `FastAPI()` is an object. `Request` and `Response` are objects. Services and
dependencies are objects.

In Playwright, `Browser`, `BrowserContext`, `Page`, and `Locator` are objects with shared
behavior and isolated state.

In AI backend systems, `ChatService`, `LLMClient`, `PromptBuilder`, `VectorStore`,
`UserRepository`, and `RedisCache` are objects or object-like components with clear
responsibilities.

The goal is not:

```text
write more classes
```

The goal is:

```text
make complex systems easier to reason about
```

---

# Roadmap Position

Day10 taught Type Hints as interface contracts.

Day11 teaches how contracts become objects and responsibilities.

```text
Day10: Type Hints
        |
        v
Day11: Object-Oriented Programming
        |
        v
Day12: Context Managers
        |
        v
FastAPI service layer
        |
        v
Playwright page objects
        |
        v
AI backend service composition
```

Type Hints describe what values flow through the system.

OOP describes who owns the values and behavior.

```text
Type Contract
      |
      v
Object Responsibility
      |
      v
Production Architecture
```

This is why Day11 comes before Context Managers, FastAPI, and larger projects.

---

# Lesson Map

```text
Today's Lesson

1. Why OOP Exists
2. Object Model Review
3. Class and Instance
4. State and Behavior
5. self
6. Attribute Lookup
7. Class Attribute vs Instance Attribute
8. Inheritance and Override
9. super()
10. MRO
11. Composition
12. FastAPI, Playwright, and AI Backend Connections
13. Interview Review
```

---

# Estimated Study Time

Reading: 90-120 minutes

Exercises: 90-120 minutes

Coding: 60-90 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Main Concepts

## Concept 1: Everything Is an Object

Day11 starts from Day01.

```text
Everything
      |
      v
    Object
```

In Python, almost everything is an object:

* integers
* strings
* lists
* functions
* classes
* modules
* exceptions
* user-created instances

Tech Lead Question:

Why would Python choose a unified object model?

Think first.

Student Answer:

"It makes the language more consistent. We can think about identity, attributes, and
behavior in a unified way."

Tech Lead Explanation:

Correct.

The unified object model lowers complexity.

Instead of learning separate mental models for values, functions, classes, and modules, we
can ask similar questions:

```text
What object is this?
What type is it?
What attributes does it have?
What behavior does it expose?
Who owns its state?
```

This is why Python feels flexible.

It is also why bad object ownership can create production bugs.

## Concept 2: Object, Class, and Instance

A class is a blueprint.

An instance is an object created from that blueprint.

```python
class User:
    pass


user = User()
```

Mental model:

```text
class User
    |
    v
creates
    |
    v
user instance
```

Classroom Coding Practice:

```python
class User:
    pass


user = User()

print(type(User))
print(type(user))
```

Expected idea:

```text
User is a class object.
user is an instance object.
```

Tech Lead Explanation:

Do not think class definitions are only templates on paper.

In Python, classes are objects too.

```text
User        -> class object
user        -> instance object
type(User)  -> type
type(user)  -> User
```

## Concept 3: State and Behavior

State is what an object knows.

Behavior is what an object can do.

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def say_hi(self) -> str:
        return f"Hi, I am {self.name}"
```

Here:

```text
state:
  self.name

behavior:
  say_hi()
```

Tech Lead Question:

Why put `name` and `say_hi()` together?

Student Answer:

"Because the behavior depends on the object's state."

Tech Lead Explanation:

Exactly.

OOP is useful when behavior and state belong together.

It is not useful when a class only wraps unrelated functions.

Production Risk:

If state ownership is unclear, different parts of the system mutate the same data and
debugging becomes painful.

## Concept 4: `self`

`self` is the current instance object.

It is not a Python keyword.

It is a naming convention.

Classroom deduction:

```python
u1.say_hi()
```

is effectively:

```python
User.say_hi(u1)
```

ASCII:

```text
u1.say_hi()
    |
    v
Python finds User.say_hi
    |
    v
passes u1 as first argument
    |
    v
User.say_hi(u1)
```

Tech Lead Question:

Why does deleting `self` cause an error?

Starter Code:

```python
class User:
    def say_hi():
        return "hi"


u1 = User()
u1.say_hi()
```

Student Think:

"Maybe Python still passes the instance, but the function has no parameter to receive it."

Tech Lead Explanation:

Exactly.

When calling `u1.say_hi()`, Python passes `u1` automatically as the first argument.

If the method does not accept `self`, the call receives one argument too many.

Common Mistake:

Thinking `self` creates the instance.

Correct:

`self` receives the current instance after the instance already exists.

## Concept 5: Class Attribute vs Instance Attribute

Class attributes live on the class.

Instance attributes live on each instance.

```python
class User:
    company = "OpenAI"

    def __init__(self, name: str) -> None:
        self.name = name
```

```python
u1 = User("Alice")
u2 = User("Bob")

print(User.company)
print(u1.company)
print(u2.company)
```

Lookup diagram:

```text
u1.company
    |
    v
instance attribute?
    |
    +-- yes -> return instance value
    |
    +-- no
          |
          v
      class attribute?
          |
          v
      return User.company
```

Classroom Question:

What happens here?

```python
u1.company = "Google"
```

Does it modify this?

```python
User.company
```

Student Answer:

"No. It creates or updates an instance attribute on `u1`, shadowing the class attribute."

Tech Lead Explanation:

Correct.

```text
User.company = "OpenAI"

u1.__dict__:
  company = "Google"

u2.__dict__:
  no company
```

So:

```text
u1.company -> "Google"
u2.company -> "OpenAI"
User.company -> "OpenAI"
```

Production Risk:

Mutable class attributes can accidentally become shared state.

Bad:

```python
class ChatSession:
    messages: list[str] = []
```

Better:

```python
class ChatSession:
    def __init__(self) -> None:
        self.messages: list[str] = []
```

Shared behavior belongs on the class.

Isolated state belongs on the instance.

## Concept 6: Attribute Lookup

Python searches attributes in an ordered way.

```text
Instance
    |
    v
Class
    |
    v
Parent
    |
    v
object
```

This explains why `u1.company` and `User.company` are different operations.

```text
u1.company
    |
    v
start from instance

User.company
    |
    v
start from class
```

Tech Lead Question:

Why does Python stop after finding the first matching attribute?

Student Answer:

"Because the closest definition wins. Otherwise attribute access would be ambiguous."

Tech Lead Explanation:

Yes.

This same rule explains method override.

## Concept 7: Method Lookup and Override

Methods are attributes too.

```python
class Browser:
    def launch(self) -> str:
        return "launch generic browser"


class Chromium(Browser):
    def launch(self) -> str:
        return "launch chromium"
```

```python
browser = Chromium()
print(browser.launch())
```

Lookup:

```text
browser.launch
    |
    v
Chromium.launch found?
    |
    v
yes -> stop
```

Expected output:

```text
launch chromium
```

Tech Lead Explanation:

Override means the child class provides a new implementation for a method inherited from
the parent.

Why does Python stop after finding `Chromium.launch()`?

Because the child implementation is the most specific behavior for that object.

## Concept 8: Inheritance

Inheritance expresses an Is-A relationship.

```text
Chromium is a Browser
```

Code:

```python
class Browser:
    def close(self) -> None:
        print("close browser")


class Chromium(Browser):
    pass
```

`Chromium` can reuse `Browser.close()`.

Why inheritance exists:

* share common behavior
* specialize behavior in child classes
* model true Is-A relationships

Production Risk:

Inheritance becomes dangerous when used only for code reuse without a real Is-A
relationship.

Bad smell:

```python
class ChatService(Database, RedisCache, LLMClient):
    ...
```

`ChatService` is not a database.

`ChatService` has a database.

That is composition.

## Concept 9: `super()`

Parent `__init__()` does not automatically run.

```python
class BaseClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout


class LLMClient(BaseClient):
    def __init__(self, timeout: int, model: str) -> None:
        self.model = model
```

Bug:

```text
LLMClient has model
LLMClient does not have timeout
```

Correct:

```python
class LLMClient(BaseClient):
    def __init__(self, timeout: int, model: str) -> None:
        super().__init__(timeout)
        self.model = model
```

Call stack diagram:

```text
LLMClient.__init__()
        |
        v
super().__init__()
        |
        v
BaseClient.__init__()
        |
        v
return
        |
        v
continue LLMClient.__init__()
```

Tech Lead Question:

Why does the parent initializer not run automatically?

Student Answer:

"Because the child class may need control over when and how the parent is initialized."

Tech Lead Explanation:

Exactly.

Python gives the child class explicit control.

That control is powerful, but forgetting `super().__init__()` is a common production bug.

## Concept 10: MRO

MRO means Method Resolution Order.

It is the order Python uses to search classes for attributes and methods.

For today's lesson, keep the mental model simple:

```text
Instance
    |
    v
Class
    |
    v
Parent
    |
    v
object
```

For multiple inheritance, MRO becomes more complex.

We do not expand complex multiple inheritance today.

Interview-safe sentence:

"Python uses MRO to provide a deterministic method lookup order, especially when
inheritance chains become more complex."

## Concept 11: Composition

Composition expresses a Has-A relationship.

```text
ChatService
    |
    +-- has Database
    +-- has Redis
    +-- has LLMClient
    +-- has PromptBuilder
    +-- has VectorStore
```

ASCII:

```text
ChatService
├── Database
├── Redis
├── LLMClient
├── PromptBuilder
└── VectorStore
```

Better:

```python
class ChatService:
    def __init__(
        self,
        database: Database,
        redis: RedisCache,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        vector_store: VectorStore,
    ) -> None:
        self.database = database
        self.redis = redis
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.vector_store = vector_store
```

Wrong direction:

```python
class ChatService(Database, RedisCache, LLMClient):
    ...
```

Tech Lead Question:

Is `ChatService` a database?

Student Answer:

"No. It uses a database."

Tech Lead Explanation:

Good.

This is the Is-A vs Has-A distinction.

Modern backend systems usually prefer composition because dependencies can be injected,
tested, replaced, and isolated.

---

# Engineering Thinking

## OOP Is Responsibility Design

OOP should answer:

```text
What state belongs here?
What behavior belongs here?
Who owns this dependency?
Can this object be tested alone?
Can this object be replaced?
```

Class is not the goal.

Responsibility is the goal.

## Shared Behavior, Isolated State

A core Day11 principle:

```text
Shared Behavior
Isolated State
```

Methods can be shared by all instances through the class.

State should usually belong to each instance.

```text
User.say_hi -> shared behavior
u1.name     -> isolated state
u2.name     -> isolated state
```

This connects back to Day07:

Data can be shared, state should not be accidentally shared.

## Composition Over Inheritance

Composition is preferred when an object uses another object.

Inheritance is appropriate when an object truly is a specialized version of another
object.

```text
Is-A  -> inheritance
Has-A -> composition
```

Production risks caused by incorrect inheritance:

* fragile base classes
* hidden coupling
* child classes depending on parent internals
* confusing lifecycle ownership
* hard-to-test objects
* accidental shared state

## Dependency Injection

Composition becomes stronger with dependency injection.

```python
service = ChatService(
    database=database,
    redis=redis,
    llm_client=llm_client,
    prompt_builder=prompt_builder,
    vector_store=vector_store,
)
```

Now dependencies are visible.

Testing becomes easier:

```python
service = ChatService(
    database=fake_database,
    redis=fake_redis,
    llm_client=fake_llm_client,
    prompt_builder=prompt_builder,
    vector_store=fake_vector_store,
)
```

## Tech Lead Review Checklist

A tech lead reviewing OOP asks:

* Does this class have one clear responsibility?
* Is this inheritance a true Is-A relationship?
* Would composition be clearer?
* Is state isolated per instance?
* Are class attributes used safely?
* Is `super().__init__()` called when required?
* Is override intentional?
* Does the object own its dependencies clearly?

## CTO Thinking

A CTO cares whether the architecture can grow.

Good OOP helps:

* isolate responsibilities
* replace dependencies
* test components independently
* onboard engineers faster
* keep framework code thin
* make AI agent systems modular

Bad OOP creates a maze of inheritance and hidden state.

---

# Classroom Exercises

## Level 1: Object

Question:

What is an object in Python?

Think First:

Does this apply only to instances created by your own classes?

Starter Code:

```python
values = [1, "hello", [], print]

for value in values:
    print(type(value))
```

Expected Output:

Different runtime types are printed. The important point is that each value is an object.

Explanation:

Python uses a unified object model.

Follow-up Question:

Why does this reduce language complexity?

## Level 2: Class and Instance

Question:

Predict the meaning of `type(User)` and `type(user)`.

Starter Code:

```python
class User:
    pass


user = User()

print(type(User))
print(type(user))
```

Expected Output:

```text
<class 'type'>
<class '__main__.User'>
```

Explanation:

`User` is a class object. `user` is an instance of `User`.

Follow-up Question:

Why is a class also an object in Python?

## Level 3: State vs Behavior

Question:

Identify state and behavior.

Starter Code:

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def say_hi(self) -> str:
        return f"Hi, I am {self.name}"
```

Expected Output:

`self.name` is state. `say_hi()` is behavior.

Explanation:

OOP is useful when behavior belongs with state.

Follow-up Question:

When would a standalone function be better than a class?

## Level 4: `self`

Question:

Explain why this fails.

Starter Code:

```python
class User:
    def say_hi():
        return "hi"


u1 = User()
u1.say_hi()
```

Expected Output:

A `TypeError` because Python passes the instance automatically, but the method does not
accept `self`.

Explanation:

```text
u1.say_hi()
    |
    v
User.say_hi(u1)
```

Follow-up Question:

Is `self` a keyword?

## Level 5: Class Attribute

Question:

Predict the output.

Starter Code:

```python
class User:
    company = "OpenAI"


u1 = User()
u2 = User()

print(u1.company)
print(u2.company)
print(User.company)
```

Expected Output:

```text
OpenAI
OpenAI
OpenAI
```

Explanation:

The instances find `company` on the class.

Follow-up Question:

When are class attributes appropriate?

## Level 6: Instance Attribute and Shadowing

Question:

Why does this not modify `User.company`?

Starter Code:

```python
class User:
    company = "OpenAI"


u1 = User()
u2 = User()

u1.company = "Google"

print(u1.company)
print(u2.company)
print(User.company)
```

Expected Output:

```text
Google
OpenAI
OpenAI
```

Explanation:

`u1.company = "Google"` creates an instance attribute that shadows the class attribute.

Follow-up Question:

Why are mutable class attributes risky?

## Level 7: Inheritance

Question:

Why can `Chromium` call `close()`?

Starter Code:

```python
class Browser:
    def close(self) -> str:
        return "close browser"


class Chromium(Browser):
    pass


browser = Chromium()
print(browser.close())
```

Expected Output:

```text
close browser
```

Explanation:

Python looks on `Chromium`, then parent `Browser`, then `object`.

Follow-up Question:

What relationship does inheritance express?

## Level 8: Method Override

Question:

Predict the output.

Starter Code:

```python
class Browser:
    def launch(self) -> str:
        return "launch generic browser"


class Chromium(Browser):
    def launch(self) -> str:
        return "launch chromium"


browser = Chromium()
print(browser.launch())
```

Expected Output:

```text
launch chromium
```

Explanation:

Python finds `Chromium.launch()` first and stops lookup.

Follow-up Question:

Why does Python not continue to `Browser.launch()`?

## Level 9: `super()`

Question:

Fix the missing parent initialization.

Starter Code:

```python
class BaseClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout


class LLMClient(BaseClient):
    def __init__(self, timeout: int, model: str) -> None:
        self.model = model
```

Expected Code:

```python
class LLMClient(BaseClient):
    def __init__(self, timeout: int, model: str) -> None:
        super().__init__(timeout)
        self.model = model
```

Explanation:

Parent `__init__()` does not run automatically.

Follow-up Question:

What production bug can happen if parent initialization is skipped?

## Level 10: Composition

Question:

Refactor this design.

Starter Code:

```python
class ChatService(Database, RedisCache, LLMClient):
    pass
```

Expected Code:

```python
class ChatService:
    def __init__(
        self,
        database: Database,
        redis: RedisCache,
        llm_client: LLMClient,
    ) -> None:
        self.database = database
        self.redis = redis
        self.llm_client = llm_client
```

Explanation:

`ChatService` has these dependencies. It is not these dependencies.

Follow-up Question:

How does dependency injection make this easier to test?

## Engineering Exercise: FastAPI Service Layer

Question:

Design a service object for user registration.

Starter Code:

```python
class UserService:
    ...
```

Expected Direction:

```python
class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def create_user(self, email: str) -> User:
        return self.repository.save(email)
```

Explanation:

The service owns business behavior and depends on a repository through composition.

Follow-up Question:

Why should the service not inherit from the repository?

## Engineering Exercise: Playwright Objects

Question:

Explain object ownership in a Playwright job.

Starter Code:

```python
async def run_job(browser: Browser) -> None:
    context = await browser.new_context()
    page = await context.new_page()
```

Expected Answer:

The job receives a shared `Browser`, creates an isolated `BrowserContext`, and creates a
`Page` inside that context.

Explanation:

Playwright uses shared behavior with isolated state.

Follow-up Question:

Why should unrelated jobs not share one `BrowserContext`?

## Engineering Exercise: AI Backend Composition

Question:

Design `ChatService` ownership.

Expected Direction:

```text
ChatService
├── Database
├── Redis
├── LLMClient
├── PromptBuilder
└── VectorStore
```

Explanation:

AI backend systems prefer composition because providers, caches, storage, and prompt
builders should be replaceable and testable.

Follow-up Question:

Which dependency would you replace with a fake during unit tests?

---

# FastAPI Connections

FastAPI uses OOP everywhere, even when route functions look functional.

## `FastAPI()` Is an Object

```python
from fastapi import FastAPI

app = FastAPI()
```

`app` is an application object.

It owns routes, middleware, dependency configuration, exception handlers, and lifecycle
hooks.

## Request and Response Objects

```python
from fastapi import Request, Response
```

`Request` represents incoming request state.

`Response` represents outgoing response behavior.

They are objects because they combine state and behavior.

## Service Layer

FastAPI route handlers should stay thin.

```text
Route
    |
    v
Service
    |
    v
Repository
```

Service object:

```python
class ChatService:
    def __init__(self, llm_client: LLMClient, repository: UserRepository) -> None:
        self.llm_client = llm_client
        self.repository = repository
```

## Dependency Injection

FastAPI prefers composition because dependencies can be injected:

```python
def get_chat_service() -> ChatService:
    return ChatService(
        llm_client=create_llm_client(),
        repository=create_user_repository(),
    )
```

This is clearer than deep inheritance.

Why FastAPI prefers composition:

* request-scoped dependencies
* replaceable services
* testable components
* explicit ownership
* less hidden coupling

---

# Playwright Connections

Playwright's object model is a practical OOP lesson.

```text
Browser
    |
    v
BrowserContext
    |
    v
Page
    |
    v
Locator
```

## Shared Behavior and Isolated State

`Browser` provides shared browser behavior.

`BrowserContext` provides isolated state:

* cookies
* local storage
* permissions
* session state

`Page` represents one tab or page inside a context.

`Locator` represents a way to find and interact with elements.

Production rule:

```text
Share Browser when appropriate.
Isolate BrowserContext per job or user.
Create Page inside the context.
Use Locator for element behavior.
```

Common bug:

Sharing one context across unrelated jobs causes login state, cookies, and local storage to
leak between jobs.

OOP helps us name ownership:

```text
Browser owns shared capability.
Context owns isolated session state.
Page owns page interaction state.
Locator owns element targeting behavior.
```

---

# English Interview

## Key Vocabulary

* object
* class
* instance
* state
* behavior
* `self`
* attribute lookup
* method lookup
* class attribute
* instance attribute
* inheritance
* method override
* `super()`
* composition
* Is-A
* Has-A
* MRO
* object ownership

## Beginner Questions

Question:

What is an object?

Standard Answer:

An object is a runtime value that has identity, type, state, and behavior.

Question:

What is the difference between a class and an instance?

Standard Answer:

A class is a blueprint and also a class object in Python. An instance is an object created
from that class.

Question:

What is `self`?

Standard Answer:

`self` is the current instance passed to an instance method. It is a convention, not a
Python keyword.

Question:

What are state and behavior?

Standard Answer:

State is the data an object owns. Behavior is what the object can do through methods.

Question:

What is the difference between class attributes and instance attributes?

Standard Answer:

Class attributes live on the class and can be shared. Instance attributes live on each
instance and represent isolated object state.

## Intermediate Questions

Question:

Explain attribute lookup.

Standard Answer:

Python looks for attributes on the instance first, then the class, then parent classes, and
eventually `object`.

Follow-up Question:

How does instance shadowing work?

Question:

Explain method lookup.

Standard Answer:

Methods are attributes. Python searches using the same lookup order and stops at the first
matching method.

Question:

Explain inheritance.

Standard Answer:

Inheritance allows a class to reuse and specialize behavior from a parent class. It should
model a true Is-A relationship.

Question:

What is method overriding?

Standard Answer:

Method overriding happens when a child class defines a method with the same name as a
parent method, replacing or specializing the behavior.

Question:

What does `super()` do?

Standard Answer:

`super()` delegates method calls to the next class in the method resolution order, often
used to call parent initialization or behavior.

Question:

Why does Python use MRO?

Standard Answer:

Python uses MRO to provide a deterministic order for attribute and method lookup,
especially in inheritance chains.

## Senior Questions

Question:

Why is composition preferred over inheritance?

Standard Answer:

Composition is preferred when an object uses other objects rather than being a specialized
version of them. It reduces coupling, improves testability, and makes dependencies
replaceable.

Production Case:

`ChatService` should have `Database`, `Redis`, and `LLMClient` dependencies instead of
inheriting from them.

Question:

Explain Is-A vs Has-A.

Standard Answer:

Is-A usually indicates inheritance. Has-A usually indicates composition.

Interview Review:

A strong answer includes design judgment, not only definitions.

Question:

How does FastAPI use OOP?

Standard Answer:

FastAPI uses application, request, response, dependency, and service objects. Even when
routes are functions, the framework relies on objects to manage state and behavior.

Question:

How does Playwright use OOP?

Standard Answer:

Playwright models browser automation through objects such as `Browser`, `BrowserContext`,
`Page`, and `Locator`, each with clear lifecycle responsibility.

Question:

How does AI Backend use composition?

Standard Answer:

AI backends often compose services from `LLMClient`, `PromptBuilder`, `VectorStore`,
`RedisCache`, repositories, and databases so dependencies can be replaced and tested.

Question:

What production risks come from incorrect inheritance?

Standard Answer:

Incorrect inheritance creates hidden coupling, fragile base classes, unclear lifecycle
ownership, accidental shared state, and hard-to-test components.

Question:

Explain object lifecycle and object ownership.

Standard Answer:

Object lifecycle describes when an object is created, used, and released. Object ownership
describes which component is responsible for creating, holding, and disposing of it.

Production Case:

In Playwright, a job may own its `BrowserContext` and `Page`, while a worker may own a
shared `Browser`.

---

# Today's Takeaway

OOP is not about writing classes everywhere.

OOP is about managing responsibility in complex systems.

```text
Object
    |
    +-- state
    +-- behavior
```

Today's core principles:

* Python uses a unified object model.
* Classes are objects.
* Instances are objects created from classes.
* `self` is the current instance.
* Attribute lookup starts from the instance and moves upward.
* Class attributes are shared through the class.
* Instance attributes isolate state per object.
* Inheritance expresses Is-A.
* Composition expresses Has-A.
* Modern backend systems usually prefer composition over inheritance.
* FastAPI, Playwright, and AI backend systems all depend on object ownership.

The most important engineering sentence:

```text
Shared behavior, isolated state.
```

---

# Before Next Lesson Checklist

Before Day12, confirm you can answer these without looking at the notes:

- [ ] What is an object?
- [ ] What is the difference between class and instance?
- [ ] What is state?
- [ ] What is behavior?
- [ ] What is `self`?
- [ ] Why does `u1.say_hi()` become `User.say_hi(u1)`?
- [ ] What is the difference between class attribute and instance attribute?
- [ ] Why does `u1.company = "Google"` not modify `User.company`?
- [ ] What is attribute lookup?
- [ ] What is method lookup?
- [ ] What is method override?
- [ ] Why does parent `__init__()` not run automatically?
- [ ] What does `super().__init__()` do?
- [ ] What is MRO?
- [ ] What is the difference between Is-A and Has-A?
- [ ] Why is composition preferred in modern backend systems?
- [ ] How does FastAPI use OOP?
- [ ] How does Playwright use OOP?
- [ ] How does AI Backend use composition?
