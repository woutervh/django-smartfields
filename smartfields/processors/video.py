import re, threading, subprocess, time, Queue

from smartfields.utils import NamedTemporaryFile


from django.core.files.base import ContentFile



class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    source: http://stefaanlippens.net/python-asynchronous-subprocess-pipe-reading
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        super(AsynchronousFileReader, self).__init__()
        self._fd = fd
        self._queue = queue

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()




class VideoConverter(object):
    task = 'convert'
    task_name = "Converting"
    responsive = True

    duration_re = "Duration: (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)"
    progress_re = "time=(?P<seconds>\d+)"

    def __init__(self, file):
        if not file:
            raise ProcessingError("There is no video file associated.")
        self.file = file


    def timedict_to_seconds(self, timedict):
        result = 0
        for key, t in timedict.iteritems():
            if key == 'seconds':
                result+= int(t)
            elif key == 'minutes':
                result+= int(t)*60
            elif key == 'hours':
                result+= int(t)*3600
        return result


    def process(self, cmd_template=None, progress_setter=None,
                progress_re=None, duration_re=None, **kwargs):
        if not cmd_template:
            raise ValueError("'cmd_template' is a required argument")
        progress_re = progress_re or self.progress_re
        duration_re = duration_re or self.duration_re
        out_file = NamedTemporaryFile(mode='rb', suffix='_%s.%s' % (
            kwargs.get('suffix', ''), kwargs.get('format', '')))
        context = kwargs.copy()
        context['input'] = self.file.path
        context['output'] = out_file.name
        cmd = cmd_template.format(**context).split()
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True)
        if progress_setter is None:
            stdout, stderr = process.communicate()
            return out_file
        stdout_queue = Queue.Queue()
        stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
        stdout_reader.start()
        duration = None
        while not stdout_reader.eof(): # or not stderr_reader.eof():
            while not stdout_queue.empty():
                line = stdout_queue.get()
                if duration is None:
                    dur = re.search(duration_re, line)
                    if dur:
                        duration = self.timedict_to_seconds(dur.groupdict())
                else:
                    prog = re.search(progress_re, line)
                    if prog:
                        seconds = self.timedict_to_seconds(prog.groupdict())
                        try:
                            progress = float(seconds)/duration
                            progress = progress if progress < 100 else 99.99
                            progress_setter(progress)
                        # Problem with output parsing.
                        # Continue, but don't set the progress
                        except ZeroDivisionError: pass
            time.sleep(1)
        stdout_reader.join()
        process.stdout.close()
        return out_file
