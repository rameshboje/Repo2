from celery_progress.backend import ProgressRecorder


class CeleryHelper:
    # Celery progress bar
    def update_progress(self, percentage, message):
        # Create progress recorder instance
        progress_recorder = ProgressRecorder(self)
        progress_recorder.set_progress(percentage, 100, description=message)

    # stop progress bar
    def stop_progress(self, percentage, exception_message):
        # Create progress recorder instance
        progress_recorder = ProgressRecorder(self)
        progress_recorder.set_progress(100, 100, description=exception_message)
