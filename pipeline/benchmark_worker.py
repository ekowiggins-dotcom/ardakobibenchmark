"""Supervised worker entry point: python -m pipeline.benchmark_worker."""
import argparse
import logging
import signal
import threading

from utils import benchmark_jobs as jobs
from utils.llm_client import get_llm_config
from pipeline.run_custom_benchmark import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Process at most one queued job and exit')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    if not get_llm_config().has_api_key:
        raise SystemExit('ANTHROPIC_API_KEY must be configured on the worker.')
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            jobs.recover_interrupted()
            job_id = jobs.next_queued()
            if job_id:
                logging.info('Processing job %s', job_id)
                run(job_id)
                logging.info('Job %s: %s', job_id, jobs.get(job_id)['status'])
            elif not args.once:
                stop.wait(5)
        except Exception as exc:
            logging.error('Worker operation failed: %s', type(exc).__name__)
            if args.once:
                raise SystemExit(1)
            stop.wait(5)
        if args.once:
            break


if __name__ == '__main__':
    main()
