set -e
cd /opt/csci-cicd
docker exec csci-jenkins cat /var/jenkins_home/workspace/container-delivery/artifacts/ecs.json > ecs-preview.json
mkdir -p preview
python3 - <<'PY'
import json,pathlib
pathlib.Path('preview/ecs-ip').write_text(json.load(open('ecs-preview.json'))['privateIp'])
PY
cat > preview/proxy.py <<'PY'
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pathlib,urllib.request,urllib.error
class Proxy(BaseHTTPRequestHandler):
 def do_GET(self):
  target=pathlib.Path('/opt/csci-cicd/preview/ecs-ip').read_text().strip()
  try:
   with urllib.request.urlopen('http://'+target+':8080'+self.path,timeout=10) as r:status=r.status;body=r.read();ctype=r.headers.get('Content-Type','text/plain')
  except urllib.error.HTTPError as r:status=r.code;body=r.read();ctype='text/plain'
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
ThreadingHTTPServer(('127.0.0.1',18081),Proxy).serve_forever()
PY
if ! pgrep -f 'python3 /opt/csci-cicd/preview/proxy.py' >/dev/null; then nohup python3 /opt/csci-cicd/preview/proxy.py > preview/proxy.log 2>&1 & fi
docker exec csci-jenkins pkill -f '^kubectl -n workshop port-forward' || true
docker exec -d -e KUBECONFIG=/var/jenkins_home/workspace/container-delivery/artifacts/kubeconfig csci-jenkins sh -c 'kubectl -n workshop port-forward --address 127.0.0.1 service/container-demo 18082:8080 > /tmp/preview-eks.log 2>&1'
wait_preview() {
  for i in {1..30}; do
    if curl -fsS --max-time 5 "http://127.0.0.1:$1/api/info"; then echo; return 0; fi
    sleep 2
  done
  echo "Preview $1 did not become ready. Check deployment and tunnel logs." >&2
  return 1
}
echo 'ECS private preview'; wait_preview 18081
echo 'EKS private preview'; wait_preview 18082
