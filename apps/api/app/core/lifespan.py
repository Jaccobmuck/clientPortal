from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # P3: DB pool init
    # P7: Redis connection init
    yield
    # P3: DB pool close
    # P7: Redis connection close
