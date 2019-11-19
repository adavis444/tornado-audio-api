#!/usr/bin/env python3

import tempfile
import wave

import mutagen.mp3
import tornado.ioloop
import tornado.web
from tornado import options


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('Main page\n')
        self.write('Valid methods and endpoints:\n')
        self.write('POST /post\n')
        self.write('GET /download\n')
        self.write('GET /list\n')
        self.write('GET /info\n')


# Add this decorator to enable streaming body support:
#@tornado.web.stream_request_body
class POSTHandler(tornado.web.RequestHandler):
    def initialize(self, database):
        self.database = database

    def post(self):
        # TODO: Process without requiring argument 'name'
        name = self.request.headers.get('name')
        if name is None:
            name = self.get_query_argument('name')
        if name in self.database:
            self.set_status(400)
            self.write('File name already in use\n')
        else:
            data = self.request.body
            with tempfile.TemporaryFile() as fp:
                fp.write(data)
                fp.seek(0)
                filetype = name.split('.')[-1]
                if filetype == 'wav':
                    with wave.open(fp, 'rb') as wave_read:
                        metadata = dict(wave_read.getparams()._asdict())
                    metadata['duration'] = (metadata['nframes']
                                            /metadata['framerate'])
                elif filetype == 'mp3':
                    mp3_read = mutagen.mp3.Open(fp)
                    metadata = mp3_read.info.__dict__
                    metadata['duration'] = metadata['length']
                else:
                    metadata = {}
            self.database[name] = metadata
            self.database[name]['_data'] = data
            self.set_status(201)


class GETHandler(tornado.web.RequestHandler):
    def _filter_database(self):
        filtered_names = []
        for name in self.database:
            file_object = self.database[name]
            for arg in self.request.query_arguments:
                if arg == 'name':
                    if self.get_query_argument('name') != name:
                        break
                elif arg == 'minduration':
                    if ('duration' not in file_object
                            or float(self.get_query_argument('minduration'))
                            > file_object['duration']):
                        break
                elif arg == 'maxduration':
                    if ('duration' not in file_object
                            or float(self.get_query_argument('maxduration'))
                            < file_object['duration']):
                        break
                elif self.get_query_argument(arg) != file_object[arg]:
                    break
            else:
                filtered_names.append(name)
        return filtered_names

    def initialize(self, database):
        self.database = database
        self.filtered_names = self._filter_database()


class DownloadHandler(GETHandler):
    def get(self):
        if self.filtered_names:
            if len(self.filtered_names) == 1:
                name = self.filtered_names[0]
                self.write(self.database[name]['_data'])
            else:
                self.set_status(400)
                self.write(
                    '{} files found.\n'.format(len(self.filtered_names)))
        else:
            self.set_status(404)
            self.write('No files found\n')


class ListHandler(GETHandler):
    def get(self):
        self.write({'list': self.filtered_names})


class InfoHandler(GETHandler):
    def get(self):
        self.write(
            {'info': [
                {name: {
                    key: value for key, value in self.database[name].items()
                    if key != '_data'}}
                for name in self.filtered_names]})


def make_app(database=None, debug=False):
    if database is None:
        database = {}
    return tornado.web.Application([
            (r'/', MainHandler),
            (r'/post', POSTHandler, dict(database=database)),
            (r'/download', DownloadHandler, dict(database=database)),
            (r'/list', ListHandler, dict(database=database)),
            (r'/info', InfoHandler, dict(database=database)),
        ],
        debug=debug,
    )


if __name__ == '__main__':
    options.parse_command_line()
    app = make_app(debug=True)
    app.listen(80)
    tornado.ioloop.IOLoop.current().start()
