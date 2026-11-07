"""Small dependency-free app used unchanged on ECS and EKS."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os
from pathlib import Path
RELEASE = json.loads(Path(__file__).with_name('release.json').read_text())
def response(path):
    info = {**RELEASE, 'commit': os.getenv('BUILD_REVISION','local'), 'platform': os.getenv('PLATFORM','local')}
    if path == '/healthz':
        return (503 if os.getenv('FORCE_UNHEALTHY') == 'true' else 200), {'status':'unhealthy' if os.getenv('FORCE_UNHEALTHY') == 'true' else 'ok'}
    if path in ('/api/info','/version'): return 200, info
    if path == '/api/compare':
        return 200, {'comparison':[
            {'capability':'Application definition','ecs':'Task definition and ECS service','eks':'Kubernetes Deployment and Service'},
            {'capability':'Scheduling','ecs':'AWS ECS scheduler on Fargate','eks':'Kubernetes scheduler on managed EC2 nodes'},
            {'capability':'Recovery','ecs':'Deployment circuit breaker rollback','eks':'Readiness probes and explicit rollout undo'},
            {'capability':'Scaling','ecs':'Service desired task count','eks':'Deployment replica count'}]}
    return 404, {'error':'not found'}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            data = (Path(__file__).with_name('index.html').read_text().replace('{{VERSION}}', RELEASE['version']).replace('{{MESSAGE}}', RELEASE['message'])).encode()
            status, content_type = 200, 'text/html; charset=utf-8'
        else:
            status, body = response(self.path.split('?')[0]); data = json.dumps(body).encode(); content_type = 'application/json'
        self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
if __name__ == '__main__': ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Handler).serve_forever()
