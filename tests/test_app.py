import importlib.util, os, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('server',Path(__file__).parents[1]/'app/server.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
class AppTests(unittest.TestCase):
    def test_health(self): self.assertEqual(app.response('/healthz'),(200,{'status':'ok'}))
    def test_bad_configuration_fails_probe(self):
        os.environ['FORCE_UNHEALTHY']='true'
        try:self.assertEqual(app.response('/healthz')[0],503)
        finally:os.environ.pop('FORCE_UNHEALTHY')
    def test_source_identity(self):
        os.environ['BUILD_REVISION']='test-sha';os.environ['PLATFORM']='EKS'
        try:
            status,data=app.response('/api/info');self.assertEqual(status,200);self.assertEqual(data['commit'],'test-sha');self.assertEqual(data['platform'],'EKS');self.assertRegex(data['version'],r'^\d+\.\d+\.\d+$')
        finally:os.environ.pop('BUILD_REVISION');os.environ.pop('PLATFORM')
    def test_not_found(self):self.assertEqual(app.response('/absent')[0],404)
if __name__=='__main__':unittest.main()
