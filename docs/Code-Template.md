# Code-Template · 可直接复制的代码模板集

> 唯一事实来源：本仓库 `cheat_sheets/python.md`、`cheat_sheets/fastapi.md`、`docs/python/day01~day14`。
> 用途：开发时直接复制。每个模板附 **何时使用 / 为何这样写 / 哪里容易改错**。

## 目录

1. [安全默认参数](#1-安全默认参数day01)
2. [Callable 配置对象](#2-callable-配置对象day01)
3. [浅拷贝 vs 深拷贝](#3-浅拷贝-vs-深拷贝day02)
4. [变异 vs 返回新对象](#4-变异-vs-返回新对象day03)
5. [闭包计数器](#5-闭包计数器day05)
6. [工厂函数](#6-工厂函数day05)
7. [晚绑定修复](#7-晚绑定修复day05)
8. [通用装饰器](#8-通用装饰器day06)
9. [重试装饰器](#9-重试装饰器day06)
10. [生成器 / 流式管道](#10-生成器--流式管道day07)
11. [异常处理与异常链](#11-异常处理与异常链day08)
12. [自定义领域异常](#12-自定义领域异常day08)
13. [项目结构 / 包布局](#13-项目结构--包布局day09)
14. [无副作用导入（工厂）](#14-无副作用导入工厂day09)
15. [类型标注 / 泛型](#15-类型标注--泛型day10)
16. [组合优于继承 / super()](#16-组合优于继承--superday11)
17. [上下文管理器](#17-上下文管理器day12)
18. [FastAPI yield 依赖](#18-fastapi-yield-依赖day12)
19. [异步并发 + Semaphore](#19-异步并发--semaphoreday13)
20. [FastAPI 薄路由 + 请求/响应模型](#20-fastapi-薄路由--请求响应模型day14)
21. [依赖注入装配](#21-依赖注入装配day14)
22. [Repository 模式](#22-repository-模式day14)
23. [长任务：task_id 状态模式](#23-长任务task_id-状态模式day14)
24. [生产并发：限流 + 指数退避](#24-生产并发限流--指数退避day14)

---

## 1. 安全默认参数（Day01）

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []          # 每次调用新建，避免跨调用共享
    items.append(item)
    return items
```

- **何时使用**：任何带默认容器（list/dict/set）参数的函数。
- **为何这样写**：默认值在函数定义时只求值一次，可变默认会跨调用共享状态。
- **易改错**：写成 `items: list[str] = []` 会导致状态泄漏；哨兵必须用 `None` 而非 `[]`。

## 2. Callable 配置对象（Day01）

```python
class Prefixer:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
    def __call__(self, value: str) -> str:
        return f"{self.prefix}{value}"

add_user_prefix = Prefixer("user:")
add_user_prefix("42")          # "user:42"
```

- **何时使用**：行为需要携带配置，又想像函数一样调用时。
- **为何这样写**：`__call__` 让实例可调用，比闭包更适合多状态场景。
- **易改错**：忘记实现 `__call__` 会 `TypeError: object is not callable`。

## 3. 浅拷贝 vs 深拷贝（Day02）

```python
import copy

shallow = copy.copy(original)       # 只拷第一层，嵌套仍共享
deep = copy.deepcopy(original)      # 递归拷贝整棵树，完全隔离
```

- **何时使用**：只需外层隔离用浅拷贝；job 需与原数据彻底隔离用深拷贝。
- **为何这样写**：明确隔离层级，避免嵌套可变态被意外共享。
- **易改错**：以为 `copy.copy()` 隔离了嵌套；盲目 `deepcopy` 昂贵且掩盖所有权不清。

## 4. 变异 vs 返回新对象（Day03）

```python
def mutate(items: list[int]) -> None:      # 改共享对象，调用者可见
    items.append(3)

def build_new(items: list[int]) -> list[int]:   # 造新对象，必须返回
    return items + [3]
```

- **何时使用**：需要改调用者数据用前者（签名 `-> None` 表意）；需要隔离用后者。
- **为何这样写**：函数边界即所有权边界，签名要表达「改它」还是「返新」。
- **易改错**：造了新对象却不 return；想隔离却用了 `append`/`+=`。

## 5. 闭包计数器（Day05）

```python
def make_counter():
    count = 0
    def counter() -> int:
        nonlocal count      # 重绑外层变量必须声明
        count += 1
        return count
    return counter
```

- **何时使用**：需要保存状态又不想用全局变量。
- **为何这样写**：闭包捕获外层环境，每个 counter 拥有独立 count。
- **易改错**：漏 `nonlocal` → `UnboundLocalError`；忘记 `return counter`（返回函数对象而非调用结果）。

## 6. 工厂函数（Day05）

```python
def make_multiplier(factor: int):
    def multiply(value: int) -> int:
        return value * factor       # 捕获配置 factor
    return multiply

double = make_multiplier(2)
```

- **何时使用**：需要参数化行为，分离配置与业务逻辑。
- **为何这样写**：支撑 FastAPI 依赖工厂、Playwright 配置工厂、AI prompt 工厂。
- **易改错**：把配置写进全局；捕获了共享可变态。

## 7. 晚绑定修复（Day05）

```python
# 错误：全部返回 2（晚绑定，调用时才查 i）
funcs = [lambda: i for i in range(3)]
# 正确：用默认参数早绑定固定当前值
fixed = [lambda i=i: i for i in range(3)]     # 0, 1, 2
```

- **何时使用**：循环中批量创建函数/回调。
- **为何这样写**：闭包捕获名字而非值，`i=i` 在定义时把当前值存为默认参数。
- **易改错**：直接捕获循环变量；以为闭包捕获的是快照。

## 8. 通用装饰器（Day06）

```python
from collections.abc import Callable
from functools import wraps
from typing import Any

def my_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)                        # 保留 __name__/__doc__/签名
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # before
        result = func(*args, **kwargs)  # 转发参数 + 保留返回值
        # after
        return result
    return wrapper
```

- **何时使用**：几乎所有生产装饰器的骨架。
- **为何这样写**：`*args/**kwargs` 通用转发，`@wraps` 保留元数据（FastAPI/inspect 依赖）。
- **易改错**：漏 `@wraps` 破坏日志与框架；漏 `return`；漏 `*args/**kwargs` 触发 TypeError。

## 9. 重试装饰器（Day06）

```python
from functools import wraps

def retry(times: int = 3):
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == times - 1:
                        raise           # 最后一次仍失败则上抛
        return wrapper
    return deco
```

- **何时使用**：Playwright 不稳定步骤、LLM 瞬时失败等**幂等**操作。
- **为何这样写**：带参装饰器三层结构（`retry(args)→deco(func)→wrapper`）。
- **易改错**：重试非幂等的写操作；静默吞掉最后的异常。

## 10. 生成器 / 流式管道（Day07）

```python
def read_pages(source):
    for page in source:
        yield process(page)        # 惰性：load one -> process one -> yield one

def parent():
    yield from read_pages(src)     # yield from 组合子生成器
    yield "done"
```

- **何时使用**：FastAPI StreamingResponse、LLM token 流、逐页抓取、大文件处理。
- **为何这样写**：惰性求值改善内存 + 首字节时间；生成器只能消费一次。
- **易改错**：用 `list()`/`sum()` 调试会消费掉生成器；需要复用却返回了生成器。

## 11. 异常处理与异常链（Day08）

```python
try:
    return call_provider()
except TimeoutError as error:
    raise LLMRequestError("LLM request timed out") from error   # 保留根因
```

- **何时使用**：把底层异常转译为领域异常时。
- **为何这样写**：`raise ... from ...` 保留根因，便于排障。
- **易改错**：转译时丢根因（漏 `from error`）；用裸 `except Exception` 吞掉未知失败。

## 12. 自定义领域异常（Day08）

```python
class InvalidPromptError(ValueError):
    pass
class LLMRequestError(RuntimeError):
    pass
class ToolExecutionError(RuntimeError):
    pass
```

- **何时使用**：大型后端需要按错误类型分类处理（映射状态码、决定重试）。
- **为何这样写**：领域异常让日志可搜索、worker 能决定 retry vs fail。
- **易改错**：所有失败塌缩成 `None`；继承基类选错（校验错误继承 `ValueError`）。

## 13. 项目结构 / 包布局（Day09）

```text
app/
├── __init__.py
├── main.py                 # 只创建 app、挂 router、配依赖
├── api/                    # Router 层（薄）
├── services/               # Service 层（无状态编排）
├── repositories/           # Repository 层（数据库抽象）
├── schemas/                # Pydantic 请求/响应模型
└── infra/                  # browser / llm 等基础设施
```

- **何时使用**：任何 FastAPI / AI 后端项目起步。
- **为何这样写**：包是架构边界，按职责划分、清晰导入边界。
- **易改错**：`__init__.py` 放连接/启动等重活；跨层导入破坏边界。

## 14. 无副作用导入（工厂）（Day09）

```python
# llm_client.py
class LLMClient:
    ...

def create_client() -> LLMClient:   # 顶层只定义，运行期才建
    return LLMClient()
```

- **何时使用**：数据库客户端、浏览器、LLM 客户端等重资源。
- **为何这样写**：导入即执行顶层代码，导入应「无聊」，重活留给运行期工厂。
- **易改错**：模块顶层连数据库/启浏览器/调 LLM，破坏测试与启动。

## 15. 类型标注 / 泛型（Day10）

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

def find_user(email: str) -> "User | None":    # 诚实的返回契约
    ...

@dataclass
class Response(Generic[T]):                     # 可复用泛型包装
    data: T
    error: str | None = None
```

- **何时使用**：公共函数边界、通用响应容器。
- **为何这样写**：类型标注是接口契约；`TypeVar` 保留输入输出关系，胜过 `object`。
- **易改错**：`-> User` 却返回 None；用裸 `list`/`dict` 隐藏元素形状；空集合忘标注。

## 16. 组合优于继承 / super()（Day11）

```python
class BaseClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

class LLMClient(BaseClient):
    def __init__(self, timeout: int, model: str) -> None:
        super().__init__(timeout)      # 父类状态不会自动初始化
        self.model = model

class ChatService:                     # Has-A：组合 + 依赖注入
    def __init__(self, llm: LLMClient, cache: "RedisCache") -> None:
        self.llm = llm
        self.cache = cache
```

- **何时使用**：Is-A 关系用继承 + `super()`；服务依赖用组合。
- **为何这样写**：现代后端偏爱组合，provider 可替换、可测试。
- **易改错**：忘 `super().__init__()` 导致父类状态未初始化；为复用而继承造成隐藏耦合。

## 17. 上下文管理器（Day12）

```python
from contextlib import contextmanager

@contextmanager
def open_file(path: str):
    f = open(path)          # Acquire
    try:
        yield f             # Use（必须在 try 内）
    finally:
        f.close()           # Release（成功失败都执行）
```

- **何时使用**：文件/连接/流/锁等需要确定性释放的资源。
- **为何这样写**：`yield` 提供 resume 相位以便后置清理；`with` 即更安全的 `try/finally`。
- **易改错**：`yield` 未包在 `try/finally` 里，异常时资源泄漏；`__exit__` 误返回 True 吞异常。

## 18. FastAPI yield 依赖（Day12）

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()          # 请求结束（含异常）都关闭
```

- **何时使用**：请求作用域的 DB session、需要收尾的资源。
- **为何这样写**：session 请求作用域，handler 只写业务，清理归依赖。
- **易改错**：清理没放 `finally`，异常时泄漏；跨请求共享 session。

## 19. 异步并发 + Semaphore（Day13）

```python
import asyncio

sem = asyncio.Semaphore(10)              # 限并发到下游容量

async def call(prompt: str):
    async with sem:
        return await call_openai(prompt)

results = await asyncio.gather(*(call(p) for p in prompts))   # 并发，按输入序返回
```

- **何时使用**：并发调用外部限流服务（OpenAI/DB/GPU）。
- **为何这样写**：`Semaphore` 防 429/超时/连接池耗尽，追求稳定吞吐。
- **易改错**：无上限 `gather` 打爆下游；`async def` 里用 `time.sleep`；调协程却不 await。

## 20. FastAPI 薄路由 + 请求/响应模型（Day14）

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()

class SummarizeRequest(BaseModel):
    url: str
class SummaryResponse(BaseModel):
    summary: str
    task_id: int

@router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    request: SummarizeRequest,
    service: "SummaryService" = Depends(get_summary_service),
) -> SummaryResponse:
    return await service.summarize(request.url)      # 只校验 + 委托
```

- **何时使用**：定义任何 FastAPI 端点。
- **为何这样写**：请求模型校验输入、响应模型控制输出，业务在 service。
- **易改错**：路由里写业务逻辑（胖路由）；在路由内构造 service 而非注入。

## 21. 依赖注入装配（Day14）

```python
def get_summary_service(
    browser: "BrowserClient" = Depends(get_browser_client),
    llm: "LLMClient" = Depends(get_llm_client),
    repo: "TaskRepository" = Depends(get_task_repository),
) -> "SummaryService":
    return SummaryService(browser=browser, llm=llm, repo=repo)
```

- **何时使用**：装配无状态服务及其依赖。
- **为何这样写**：`Depends()` 是请求作用域依赖注入，支持测试用假实现、生产换 provider。
- **易改错**：在路由/服务内部 `new` 依赖，导致不可测试、耦合。

## 22. Repository 模式（Day14）

```python
class TaskRepository:
    async def save_task(self, url: str, summary: str) -> "Task":
        ...
    async def get_task(self, task_id: int) -> "Task | None":
        ...
```

- **何时使用**：任何持久化读写。
- **为何这样写**：隐藏数据库，返回领域对象而非原始行，service 永不写 SQL。
- **易改错**：把 SQL 向上层泄漏；返回 ORM 原始行而非领域对象。

## 23. 长任务：task_id 状态模式（Day14）

```text
POST /summarize   -> 立即返回 task_id
GET  /tasks/{id}  -> 返回任务状态/结果
Worker            -> 拉取任务、运行 service、更新状态
```

- **何时使用**：耗时的 LLM/抓取任务（>数秒）。
- **为何这样写**：队列 + worker + 状态让 API 保持响应，不长时间占用连接。
- **易改错**：用一个 30 秒阻塞请求处理长任务，导致超时、连接堆积。

## 24. 生产并发：限流 + 指数退避（Day14）

```python
import asyncio

sem = asyncio.Semaphore(10)

async def call(url: str):
    async with sem:
        for attempt in range(5):
            try:
                return await service.summarize(url)
            except RateLimitError:
                await asyncio.sleep(2 ** attempt)    # 指数退避
        raise
```

- **何时使用**：批量调用有速率限制的外部服务。
- **为何这样写**：`Semaphore` 限并发，429 用指数退避重试，优化稳定吞吐。
- **易改错**：追求最大并发而非稳定吞吐；不区分瓶颈（限流/DB 池/浏览器内存）盲目加并发。

---

## 附：模板选择速查

| 场景 | 用哪个模板 |
|------|-----------|
| 带默认容器参数 | #1 安全默认参数 |
| 需要保存状态不用全局 | #5 闭包计数器 / #6 工厂函数 |
| 加日志/计时/重试/鉴权 | #8 通用装饰器 / #9 重试装饰器 |
| 流式下发 / token 流 | #10 生成器管道 |
| 底层异常转领域异常 | #11 异常链 / #12 领域异常 |
| 资源必须释放 | #17 上下文管理器 / #18 yield 依赖 |
| 并发调外部 API | #19 Semaphore / #24 限流退避 |
| 新建 FastAPI 端点 | #20 薄路由 / #21 依赖注入 / #22 Repository |
| 耗时任务 | #23 task_id 状态模式 |
