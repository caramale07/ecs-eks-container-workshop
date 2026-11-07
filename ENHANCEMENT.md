# Implement the enhancement locally in VS Code

To run any named VS Code task, open **Terminal** in the VS Code top menu bar, choose **Run Task…**, and select the task. On macOS, Terminal is at the very top of the screen next to Run; do not choose the Run menu. You can also press Command+Shift+P on macOS or Ctrl+Shift+P on Windows/Linux, type **Tasks: Run Task**, and select it. The circular arrow in an existing task terminal reruns that terminal’s current task.

Start from the supplied starter at version 1.0.0. Create branch `enhancement/platform-comparison` using the status bar. Keep a copy of the completed example available in a separate VS Code window for reference.

1. In Explorer open `app/release.json`. Change version to `2.0.0` and set a message describing your comparison feature. Save.
2. In `app/server.py`, inside `response`, immediately before its final `return 404`, add the endpoint below. Keep indentation consistent.

```python
    if path == '/api/compare':
        return 200, {'comparison':[
            {'capability':'Application definition','ecs':'Task definition and ECS service','eks':'Kubernetes Deployment and Service'},
            {'capability':'Scheduling','ecs':'AWS ECS scheduler on Fargate','eks':'Kubernetes scheduler on managed EC2 nodes'},
            {'capability':'Recovery','ecs':'Deployment circuit breaker rollback','eks':'Readiness probes and explicit rollout undo'},
            {'capability':'Scaling','ecs':'Service desired task count','eks':'Deployment replica count'}]}
```

3. In `tests/test_app.py`, add a test inside `AppTests` before its `test_not_found` method:

```python
    def test_comparison_enhancement(self):
        status, data = app.response('/api/compare')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['comparison']), 4)
        self.assertTrue(all(row['ecs'] and row['eks'] for row in data['comparison']))
```

4. The starter already includes the web interface. Read its refresh function: it fetches `/api/info`, `/healthz` and `/api/compare`. The comparison rows appear when your new endpoint exists.
5. In the VS Code top menu bar choose Terminal > Run Task… > 4 Test application. Five tests must pass. Then choose Terminal > Run Task… > Preview local enhancement and inspect the page at http://127.0.0.1:18083. The starter server supports the PORT variable so it can use that task.
6. Source Control: inspect your local diff, Commit, Publish Branch. Create the PR, wait for CI and merge to main. Verify Jenkins and both deployed applications.

Explain the API, test and interface relationship in your submission. Merely changing a version number is not the full enhancement.
