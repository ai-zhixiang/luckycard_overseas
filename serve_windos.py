import http.server, socketserver, os

os.chdir('/home/ubuntu/luckycardeng/app/static')

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/windos-build.zip':
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="windos-build.zip"')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'keep-alive')
            with open('windos-build.zip', 'rb') as f:
                fs = os.fstat(f.fileno())
                self.send_header('Content-Length', str(fs.st_size))
                self.end_headers()
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('0.0.0.0', 9999), Handler) as httpd:
    httpd.serve_forever()
