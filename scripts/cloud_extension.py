#!/usr/bin/env python3
"""Controlled health failure, rollback, scaling and release verification in the lab."""
import json,os,time,subprocess
import lab
c=lab.config();image=lab.load('image');ecs_before=lab.load('ecs');eks_before=lab.load('eks')
os.environ['KUBECONFIG']=str(lab.A.absolute()/'kubeconfig')
result={'exercise':'Cloud Computing recovery and scale comparison','commit':image['commit'],'digest':image['digest']}
# Kubernetes leaves a failed rollout visible; the pipeline must explicitly undo it.
print('EKS: inject a failed health configuration',flush=True)
lab.kube('set','env','deployment/'+lab.SERVICE,'FORCE_UNHEALTHY=true')
r=subprocess.run(['kubectl','-n',lab.NS,'rollout','status','deployment/'+lab.SERVICE,'--timeout=120s'],text=True,capture_output=True)
if r.returncode==0:raise SystemExit('Expected the intentionally unhealthy rollout to fail')
result['eks_failed_rollout']=r.stdout+r.stderr
result['eks_failure_state']=json.loads(lab.kube('get','deployment',lab.SERVICE,'-o','json'))['status']
print('EKS: undo failed rollout',flush=True);print(lab.kube('rollout','undo','deployment/'+lab.SERVICE));print(lab.kube('rollout','status','deployment/'+lab.SERVICE,'--timeout=180s'))
result['eks_rollback']='explicit rollout undo restored availability'
# ECS deployment circuit breaker is configured to restore the prior task definition.
print('ECS: inject a failed health configuration',flush=True)
base=lab.aws('ecs','describe-task-definition','--task-definition',ecs_before['taskDefinition'])['taskDefinition']
keys=['family','taskRoleArn','executionRoleArn','networkMode','containerDefinitions','volumes','placementConstraints','requiresCompatibilities','cpu','memory','runtimePlatform','ephemeralStorage']
bad={k:base[k] for k in keys if k in base}
bad['containerDefinitions'][0]['environment'].append({'name':'FORCE_UNHEALTHY','value':'true'})
bad_arn=lab.aws('ecs','register-task-definition','--cli-input-json',json.dumps(bad))['taskDefinition']['taskDefinitionArn']
lab.aws('ecs','update-service','--cluster',c['EcsCluster'],'--service',lab.SERVICE,'--task-definition',bad_arn)
failed_seen=False
for _ in range(80):
 time.sleep(10)
 service=lab.aws('ecs','describe-services','--cluster',c['EcsCluster'],'--services',lab.SERVICE)['services'][0]
 failed_seen=failed_seen or any(d['taskDefinition']==bad_arn and d.get('rolloutState')=='FAILED' for d in service['deployments'])
 primary=next(d for d in service['deployments'] if d['status']=='PRIMARY')
 if primary['taskDefinition']==ecs_before['taskDefinition'] and primary.get('rolloutState')=='COMPLETED':
  result['ecs_rollback']='deployment circuit breaker restored prior task definition';result['ecs_events']=service.get('events',[])[:12];break
else:raise SystemExit('ECS automatic rollback did not complete within the lab timeout')
result['ecs_failed_task_definition']=bad_arn;result['ecs_failure_state_seen']=failed_seen
print('Both platforms recovered. Scale to two replicas/tasks.',flush=True)
lab.aws('ecs','update-service','--cluster',c['EcsCluster'],'--service',lab.SERVICE,'--desired-count','2')
print(lab.kube('scale','deployment/'+lab.SERVICE,'--replicas=2'))
lab.aws('ecs','wait','services-stable','--cluster',c['EcsCluster'],'--services',lab.SERVICE)
print(lab.kube('rollout','status','deployment/'+lab.SERVICE,'--timeout=180s'))
service=lab.aws('ecs','describe-services','--cluster',c['EcsCluster'],'--services',lab.SERVICE)['services'][0]
dep=json.loads(lab.kube('get','deployment',lab.SERVICE,'-o','json'))
assert service['runningCount']==2 and dep['status']['readyReplicas']==2
result['scale_result']={'ecs_running_tasks':service['runningCount'],'eks_ready_replicas':dep['status']['readyReplicas']}
print('Restore one replica/task to limit lab cost.',flush=True)
lab.aws('ecs','update-service','--cluster',c['EcsCluster'],'--service',lab.SERVICE,'--desired-count','1')
lab.kube('scale','deployment/'+lab.SERVICE,'--replicas=1')
lab.aws('ecs','wait','services-stable','--cluster',c['EcsCluster'],'--services',lab.SERVICE)
lab.kube('rollout','status','deployment/'+lab.SERVICE,'--timeout=180s')
# Refresh the dynamic task and pod addresses after recovery, then re-verify identity.
ids=lab.aws('ecs','list-tasks','--cluster',c['EcsCluster'],'--service-name',lab.SERVICE,'--desired-status','RUNNING')['taskArns']
task=lab.aws('ecs','describe-tasks','--cluster',c['EcsCluster'],'--tasks',*ids)['tasks'][0]
ecs_before.update({'task':task['taskArn'],'taskDefinition':task['taskDefinitionArn'],'privateIp':next(p['value'] for a in task['attachments'] for p in a['details'] if p['name']=='privateIPv4Address'),'imageDigest':task['containers'][0]['imageDigest']});lab.save('ecs',ecs_before)
pods=json.loads(lab.kube('get','pods','-l','app='+lab.SERVICE,'-o','json'))['items']
pod=next(p for p in pods if not p['metadata'].get('deletionTimestamp') and p.get('status',{}).get('containerStatuses') and all(s['ready'] for s in p['status']['containerStatuses']))
eks_before.update({'pod':pod['metadata']['name'],'imageID':pod['status']['containerStatuses'][0]['imageID'],'image':pod['spec']['containers'][0]['image']});lab.save('eks',eks_before)
lab.verify();result['final_health']='PASS';lab.save('cloud-extension',result)
if c.get('AuditBucket'):
 lab.aws('s3api','put-object','--bucket',c['AuditBucket'],'--key','releases/'+image['commit']+'/cloud-extension.json','--body',str(lab.A/'cloud-extension.json'),'--server-side-encryption','AES256')
 result['audit_bucket']=c['AuditBucket'];lab.save('cloud-extension',result)
print(json.dumps(result,indent=2))
