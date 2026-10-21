import asyncio
import time
from dataclasses import dataclass

from database import save_predictions
from schemas import CandidateRequest, PredictionResponse
from services import make_prediction

MAX_BATCH_SIZE = 8
MAX_BATCH_WAIT_MS = 50
QUEUE_MAX_SIZE = 100
INFERENCE_TIMEOUT_SECONDS = 2.0


@dataclass
class InferenceTask:
    request_id: str
    payload: CandidateRequest
    future: asyncio.Future[PredictionResponse]


class DynamicBatchQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[InferenceTask] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self.worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    async def submit(self, request_id: str, payload: CandidateRequest) -> PredictionResponse:
        if self.queue.full():
            raise OverflowError
        future: asyncio.Future[PredictionResponse] = asyncio.get_running_loop().create_future()
        self.queue.put_nowait(InferenceTask(request_id=request_id, payload=payload, future=future))
        return await asyncio.wait_for(asyncio.shield(future), timeout=INFERENCE_TIMEOUT_SECONDS)

    async def _worker(self) -> None:
        while True:
            first = await self.queue.get()
            batch = [first]
            deadline = time.monotonic() + MAX_BATCH_WAIT_MS / 1000
            while len(batch) < MAX_BATCH_SIZE:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self.queue.get(), timeout=remaining))
                except asyncio.TimeoutError:
                    break
            try:
                results = [make_prediction(task.request_id, task.payload) for task in batch]
                await save_predictions(results, source="dynamic_batch")
                for task, result in zip(batch, results):
                    if not task.future.done():
                        task.future.set_result(result)
            except Exception as exc:
                for task in batch:
                    if not task.future.done():
                        task.future.set_exception(exc)
            finally:
                for _ in batch:
                    self.queue.task_done()


dynamic_queue = DynamicBatchQueue()
