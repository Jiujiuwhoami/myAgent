"""Graceful Shutdown and Interrupt Handling

Support:
- SIGINT (Ctrl+C) handling
- SIGTERM (kill) handling
- Emergency checkpoint save
- Graceful shutdown hooks
"""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional


class GracefulShutdown:
    """
    Graceful shutdown manager

    Example:
        shutdown = GracefulShutdown(runtime)
        shutdown.setup()
    """

    def __init__(
        self,
        checkpoint_callback: Optional[Callable] = None,
        cleanup_callback: Optional[Callable] = None,
        checkpoint_dir: str = "checkpoints",
    ):
        self.checkpoint_callback = checkpoint_callback
        self.cleanup_callback = cleanup_callback
        self.checkpoint_dir = Path(checkpoint_dir)
        self.interrupted = False
        self.interrupt_count = 0
        self._original_handlers = {}
        self._shutdown_hooks: List[Callable] = []

    def setup(self):
        """Setup signal handlers"""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self._handle_signal)
        self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self._handle_signal)

        print("   [OK] Graceful shutdown enabled (Press Ctrl+C to save state and exit)")

    def restore(self):
        """Restore original signal handlers"""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def register_shutdown_hook(self, hook: Callable):
        """Register shutdown hook"""
        self._shutdown_hooks.append(hook)

    def _handle_signal(self, signum, frame):
        """Handle interrupt signal"""
        self.interrupt_count += 1
        sig_name = signal.Signals(signum).name

        if self.interrupt_count == 1:
            print(f"\n[WARNING] Received {sig_name} signal, saving state...")
            self.interrupted = True

            asyncio.create_task(self._emergency_save())

            if self.interrupt_count >= 3:
                print("\n[WARNING] Force exit (Ctrl+C pressed 3 times)")
                self._force_exit()
        else:
            print(f"\n[WARNING] Received {sig_name} signal again")

    async def _emergency_save(self):
        """Emergency save checkpoint"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        emergency_cp = {
            "type": "emergency",
            "timestamp": timestamp,
            "interrupt_count": self.interrupt_count,
        }

        if self.checkpoint_callback:
            try:
                state = self.checkpoint_callback()
                emergency_cp["state"] = state
                print("   [OK] State saved to checkpoint")
            except Exception as e:
                print(f"   [ERROR] Failed to save checkpoint: {e}")

        cp_file = self.checkpoint_dir / f"emergency_{timestamp}.json"
        try:
            with open(cp_file, "w", encoding="utf-8") as f:
                json.dump(emergency_cp, f, indent=2, default=str, ensure_ascii=False)
            print(f"   [FILE] Emergency checkpoint: {cp_file.name}")
        except Exception as e:
            print(f"   [ERROR] Failed to save checkpoint file: {e}")

        for hook in self._shutdown_hooks:
            try:
                hook()
            except Exception as e:
                print(f"   [ERROR] Shutdown hook failed: {e}")

        await asyncio.sleep(0.5)
        self._graceful_exit()

    def _graceful_exit(self):
        """Graceful exit"""
        print("\n[BYE] Goodbye!")
        self.restore()
        sys.exit(0)

    def _force_exit(self):
        """Force exit"""
        print("\n[EXIT] Force exit")
        self.restore()
        os._exit(1)


class InterruptibleTask:
    """
    Interruptible task wrapper

    Example:
        async def my_task():
            async with InterruptibleTask() as it:
                for item in items:
                    if it.interrupted:
                        break
                    await process(item)
    """

    def __init__(self, shutdown_manager: Optional[GracefulShutdown] = None):
        self.shutdown_manager = shutdown_manager
        self._interrupted = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.shutdown_manager:
            self._interrupted = self.shutdown_manager.interrupted
        return False

    @property
    def interrupted(self) -> bool:
        return self._interrupted or (self.shutdown_manager and self.shutdown_manager.interrupted)

    def check(self) -> bool:
        """Check if interrupted"""
        if self.interrupted:
            return True
        if self.shutdown_manager:
            return self.shutdown_manager.interrupted
        return False


class ProgressCheckpoint:
    """
    Progress checkpoint - for saving long-running task progress

    Example:
        checkpoint = ProgressCheckpoint("my_task", checkpoint_dir="checkpoints")
        checkpoint.save(progress=50, data={"step": "processing"})

        # Restore
        state = checkpoint.load()
        if state:
            resume_from = state["progress"]
    """

    def __init__(self, task_name: str, checkpoint_dir: str = "checkpoints"):
        self.task_name = task_name
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / f"{task_name}_progress.json"

    def save(self, progress: int, data: dict, metadata: Optional[dict] = None):
        """Save progress"""
        state = {
            "task_name": self.task_name,
            "progress": progress,
            "data": data,
            "metadata": metadata or {},
            "saved_at": datetime.now().isoformat(),
            "interrupted": False,
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        print(f"   [OK] Progress saved: {progress}%")

    def mark_interrupted(self):
        """Mark as interrupted"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                state["interrupted"] = True
                state["interrupted_at"] = datetime.now().isoformat()
                with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
            except:
                pass

    def load(self) -> Optional[dict]:
        """Load progress"""
        if not self.checkpoint_file.exists():
            return None

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"   [ERROR] Failed to load progress: {e}")
            return None

    def clear(self):
        """Clear checkpoint"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            print("   [OK] Checkpoint cleared")

    def exists(self) -> bool:
        """Check if exists"""
        return self.checkpoint_file.exists()


class TaskResumer:
    """
    Task resumer

    Example:
        resumer = TaskResumer(checkpoint_dir="checkpoints")

        # Check if there are recoverable tasks
        if resumer.has_recoverable("my_task"):
            state = resumer.load_state("my_task")
            # Resume execution
            resume_from_step(state["progress"])
    """

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)

    def list_recoverable(self) -> List[dict]:
        """List all recoverable tasks"""
        recoverable = []

        if not self.checkpoint_dir.exists():
            return recoverable

        for f in self.checkpoint_dir.glob("*_progress.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    state = json.load(fp)
                    recoverable.append(
                        {
                            "task_name": state.get("task_name", f.stem.replace("_progress", "")),
                            "progress": state.get("progress", 0),
                            "saved_at": state.get("saved_at"),
                            "was_interrupted": state.get("interrupted", False),
                        }
                    )
            except:
                pass

        return sorted(recoverable, key=lambda x: x.get("saved_at", ""), reverse=True)

    def has_recoverable(self, task_name: str) -> bool:
        """Check if task is recoverable"""
        checkpoint_file = self.checkpoint_dir / f"{task_name}_progress.json"
        if not checkpoint_file.exists():
            return False

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            return state.get("interrupted", False)
        except:
            return False

    def load_state(self, task_name: str) -> Optional[dict]:
        """Load task state"""
        checkpoint_file = self.checkpoint_dir / f"{task_name}_progress.json"
        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None

    def delete_state(self, task_name: str):
        """Delete task state"""
        checkpoint_file = self.checkpoint_dir / f"{task_name}_progress.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()


def demo():
    """Demo"""
    print("=" * 60)
    print("Graceful Shutdown and Interrupt Handling Demo")
    print("=" * 60)

    print("\n1. GracefulShutdown Demo:")
    print("   - Press Ctrl+C to auto-save checkpoint")
    print("   - Press 3 times to force exit")

    print("\n2. ProgressCheckpoint Demo:")
    checkpoint = ProgressCheckpoint("demo_task")
    checkpoint.save(progress=50, data={"step": "processing", "items": [1, 2, 3]})
    state = checkpoint.load()
    print(f"   Loaded state: progress={state['progress']}%")

    print("\n3. TaskResumer Demo:")
    resumer = TaskResumer()
    recoverable = resumer.list_recoverable()
    print(f"   Recoverable tasks: {len(recoverable)}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo()
