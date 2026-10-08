"""One collector execution boundary, including setup failures and finalization."""
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
import logging
import signal
import sys
from threading import current_thread, main_thread
from time import monotonic

from database.repositories.collection_runs import CollectionLockLost

LOGGER = logging.getLogger(__name__)
_current = ContextVar('collection_control', default=None)


class CollectionStop(KeyboardInterrupt):
    """Cooperative stop shares the collector's Ctrl-C checkpoint path."""


class WorkerControl:
    def __init__(self, runs, lease, interval=30):
        self.runs, self.lease, self.interval = runs, lease, interval
        self.run_id = self.worker_token = None
        self.last_poll = float('-inf')
        self.status = 'failed'
        self.reason = None
        self.shutdown_requested = False
        self.progress = None

    def bind(self, run_id):
        self.run_id = run_id
        self.worker_token = self.runs.control(run_id).worker_token
        self.check(force=True)

    def check(self, force=False):
        if self.shutdown_requested:
            self.reason = "process_shutdown"
            raise CollectionStop()
        if self.run_id is None:
            return
        tick = monotonic()
        if not force and tick - self.last_poll < self.interval:
            return
        if self.lease is not None:
            self.lease.check()
        run = self.runs.control(self.run_id)
        if run is None or run.status != 'running' or run.worker_token != self.worker_token:
            raise CollectionLockLost('Collection attempt is no longer current')
        if tick - self.last_poll >= self.interval:
            self.runs.heartbeat(self.run_id, self.worker_token, datetime.now(timezone.utc))
            self.last_poll = tick
        if run.stop_requested_at:
            self.reason = 'user_requested_stop'
            raise CollectionStop()


def checkpoint(*, force=False):
    control = _current.get()
    if control:
        control.check(force)


def bind_run(run_id):
    _current.get().bind(run_id)


def terminal_status(status):
    control = _current.get()
    control.status = status
    if status == "interrupted" and control.reason is None:
        control.reason = "keyboard_interrupt"


def managed_collection(function):
    """Acquire ownership before resolving a row; always finalize owned executions."""
    spec = signature(function)

    @wraps(function)
    def wrapper(*args, **kwargs):
        values = spec.bind(*args, **kwargs)
        values.apply_defaults()
        if values.arguments.get('services') is None:
            from scripts.trial_scraper import build_services
            values.arguments['services'] = build_services()
        if values.arguments.get('run_name') is None:
            values.arguments['run_name'] = datetime.now(timezone.utc).strftime('trial-%Y%m%dT%H%M%S%fZ')
        runs = values.arguments['services'][2]
        with runs.lock(values.arguments['run_name']) as lease:
            control = WorkerControl(runs, lease)
            token = _current.set(control)
            previous_sigterm = None
            if current_thread() is main_thread():
                def request_shutdown(signum, frame):
                    # No I/O or exception inside an in-flight durable write.
                    control.shutdown_requested = True
                previous_sigterm = signal.signal(signal.SIGTERM, request_shutdown)
            try:
                result = function(*values.args, **values.kwargs)
                return result
            except BaseException as exc:
                control.status = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit, CollectionLockLost)) else 'failed'
                control.reason = control.reason or ('lease_lost' if isinstance(exc, CollectionLockLost)
                                                    else 'process_interrupted' if control.status == 'interrupted'
                                                    else 'execution_or_checkpoint_failed')
                # Setup/recovery can exit before a collector's inner checkpoint handler.
                if control.progress is not None:
                    state, objects, name = control.progress
                    state['status'] = control.status
                    state['stop_reason'] = control.reason
                    state['updated_at'] = datetime.now(timezone.utc).isoformat()
                    for scan in state.get('scans', {}).values():
                        if scan['status'] == 'running':
                            scan['status'] = 'pending'
                    try:
                        objects.write_json('runs', name, state)
                    except Exception as checkpoint_error:
                        LOGGER.warning('collection_emergency_checkpoint_failed error_type=%s',
                                       type(checkpoint_error).__name__)
                raise
            finally:
                _current.reset(token)
                if previous_sigterm is not None:
                    signal.signal(signal.SIGTERM, previous_sigterm)
                if control.run_id is not None:
                    unwinding = sys.exc_info()[0] is not None
                    try:
                        # Lost owners must never finalize a successor's attempt.
                        if lease is not None:
                            lease.check()
                        runs.set_status(control.run_id, control.status, reason=control.reason,
                                        worker_token=control.worker_token)
                    except Exception as exc:
                        LOGGER.warning('collection_finalization_failed error_type=%s', type(exc).__name__)
                        # Never return success when the terminal database write failed.
                        if not unwinding:
                            raise
    return wrapper


def interruption_reason():
    return _current.get().reason or "keyboard_interrupt"


def assert_ownership():
    """Allow durable flush after Stop, but refuse writes by a lost lock owner."""
    control = _current.get()
    if control and control.lease is not None:
        control.lease.check()



def register_progress(state, objects, name):
    """Retain actual loaded counters for interrupted setup/recovery, without guessing."""
    _current.get().progress = (state, objects, name)
