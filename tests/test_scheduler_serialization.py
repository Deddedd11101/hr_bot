import asyncio
import unittest
from unittest.mock import patch

from app import scheduler


class SchedulerSerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_and_step_share_delivery_serialization(self):
        self.assertTrue(hasattr(scheduler.schedule_all_employees, "__wrapped__"))
        self.assertTrue(hasattr(scheduler.run_scheduled_step, "__wrapped__"))
        started = asyncio.Event()
        release = asyncio.Event()
        second_started = asyncio.Event()

        @scheduler._serialize_scheduler_delivery
        async def first():
            started.set()
            await release.wait()

        @scheduler._serialize_scheduler_delivery
        async def second():
            second_started.set()

        with patch.object(scheduler, "_scheduler_delivery_lock", asyncio.Lock()):
            first_task = asyncio.create_task(first())
            await asyncio.wait_for(started.wait(), timeout=2)
            second_task = asyncio.create_task(second())
            try:
                await asyncio.sleep(0)
                self.assertFalse(second_started.is_set())
            finally:
                release.set()
                await asyncio.wait_for(asyncio.gather(first_task, second_task), timeout=2)
            self.assertTrue(second_started.is_set())

    async def test_failed_delivery_releases_lock(self):
        @scheduler._serialize_scheduler_delivery
        async def failure():
            raise RuntimeError("delivery failed")

        @scheduler._serialize_scheduler_delivery
        async def next_delivery():
            return "completed"

        with patch.object(scheduler, "_scheduler_delivery_lock", asyncio.Lock()):
            with self.assertRaises(RuntimeError):
                await failure()
            self.assertEqual(await asyncio.wait_for(next_delivery(), timeout=2), "completed")
