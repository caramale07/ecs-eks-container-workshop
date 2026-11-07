#!/usr/bin/env python3
"""AWS CLI based deployment of the same immutable release to ECS and EKS."""
import json,os,pathlib,subprocess,sys,time,urllib.request
os.environ.setdefault('AWS_DEFAULT_REGION','us-east-1');os.environ['AWS_PAGER']=''
REGION=os.environ['AWS_DEFAULT_REGION'];STACK=os.getenv('LAB_STACK','csci-ecs-eks-cicd');NS='workshop';SERVICE='container-demo'
A=pathlib.Path('artifacts');A.mkdir(exist_ok=True)
def run(args,**kwargs):return subprocess.check_output(args,text=True,**kwargs).strip()
def aws(*args,**kw):
    s=run(['aws',*args,'--output','json'],**kw);return json.loads(s) if s else None
def save(name,obj): (A/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
def load(name): return json.loads((A/(name+'.json')).read_text())
def config():
    s=aws('cloudformation','describe-stacks','--stack-name',STACK)['Stacks'][0]
    c={x['OutputKey']:x['OutputValue'] for x in s['Outputs']};c['account']=aws('sts','get-caller-identity')['Account'];return c
def kube(*args,**kw):return run(['kubectl','--namespace',NS,*args],**kw)
def build():
    c=config();sha=run(['git','rev-parse','HEAD']);tag=c['EcrUri']+':'+sha
    try:d=aws('ecr','describe-images','--repository-name','csci-container-lab','--image-ids','imageTag='+sha)['imageDetails'][0]['imageDigest']
    except subprocess.CalledProcessError:
        subprocess.run(['docker','build','--platform','linux/amd64','--build-arg','BUILD_REVISION='+sha,'-t',tag,'.'],check=True)
        password=run(['aws','ecr','get-login-password','--region',REGION])
        subprocess.run(['docker','login','--username','AWS','--password-stdin',c['EcrUri'].split('/')[0]],input=password,text=True,check=True)
        subprocess.run(['docker','push',tag],check=True)
        d=aws('ecr','describe-images','--repository-name','csci-container-lab','--image-ids','imageTag='+sha)['imageDetails'][0]['imageDigest']
    v={'commit':sha,'digest':d,'image':c['EcrUri']+'@'+d,'tag':tag};save('image',v);print(json.dumps(v,indent=2))
def ecs():
    c=config();v=load('image');role='arn:aws:iam::'+c['account']+':role/LabRole'
    task={'family':SERVICE,'networkMode':'awsvpc','requiresCompatibilities':['FARGATE'],'cpu':'256','memory':'512','taskRoleArn':role,'executionRoleArn':role,'containerDefinitions':[{'name':'app','image':v['image'],'essential':True,'readonlyRootFilesystem':True,'user':'10001:10001','portMappings':[{'containerPort':8080,'protocol':'tcp'}],'environment':[{'name':'PLATFORM','value':'ECS'}],'healthCheck':{'command':['CMD-SHELL',"python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2)\""],'interval':5,'timeout':3,'retries':2,'startPeriod':10},'logConfiguration':{'logDriver':'awslogs','options':{'awslogs-group':c['LogGroup'],'awslogs-region':REGION,'awslogs-stream-prefix':'app'}}}]}
    t=aws('ecs','register-task-definition','--cli-input-json',json.dumps(task))['taskDefinition']['taskDefinitionArn']
    found=aws('ecs','describe-services','--cluster',c['EcsCluster'],'--services',SERVICE)['services']
    deploy={'deploymentCircuitBreaker':{'enable':True,'rollback':True},'maximumPercent':200,'minimumHealthyPercent':100}
    if found and found[0]['status']=='ACTIVE':aws('ecs','update-service','--cluster',c['EcsCluster'],'--service',SERVICE,'--task-definition',t,'--deployment-configuration',json.dumps(deploy))
    else:aws('ecs','create-service','--cluster',c['EcsCluster'],'--service-name',SERVICE,'--task-definition',t,'--desired-count','1','--launch-type','FARGATE','--deployment-configuration',json.dumps(deploy),'--network-configuration',json.dumps({'awsvpcConfiguration':{'subnets':c['SubnetIds'].split(','),'securityGroups':[c['AppSecurityGroup']],'assignPublicIp':'ENABLED'}}))
    aws('ecs','wait','services-stable','--cluster',c['EcsCluster'],'--services',SERVICE)
    ids=aws('ecs','list-tasks','--cluster',c['EcsCluster'],'--service-name',SERVICE,'--desired-status','RUNNING')['taskArns']
    tasks=aws('ecs','describe-tasks','--cluster',c['EcsCluster'],'--tasks',*ids)['tasks']
    task=next(x for x in tasks if x['taskDefinitionArn']==t)
    ip=next(p['value'] for a in task['attachments'] for p in a['details'] if p['name']=='privateIPv4Address')
    result={'task':task['taskArn'],'taskDefinition':t,'privateIp':ip,'imageDigest':task['containers'][0].get('imageDigest'),'expected':v};save('ecs',result);print(json.dumps(result,indent=2))
def eks():
    c=config();v=load('image')
    os.environ['KUBECONFIG']=str(A.absolute()/'kubeconfig')
    run(['aws','eks','update-kubeconfig','--name',c['EksCluster'],'--kubeconfig',os.environ['KUBECONFIG']])
    doc={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':SERVICE,'namespace':NS},'spec':{'replicas':1,'revisionHistoryLimit':3,'progressDeadlineSeconds':90,'selector':{'matchLabels':{'app':SERVICE}},'template':{'metadata':{'labels':{'app':SERVICE},'annotations':{'workshop/source-commit':v['commit']}},'spec':{'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'app','image':v['image'],'ports':[{'containerPort':8080}],'env':[{'name':'PLATFORM','value':'EKS'}],'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'250m','memory':'128Mi'}},'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'readinessProbe':{'httpGet':{'path':'/healthz','port':8080},'initialDelaySeconds':2,'periodSeconds':5},'livenessProbe':{'httpGet':{'path':'/healthz','port':8080},'initialDelaySeconds':10,'periodSeconds':10}}]}}}}
    service={'apiVersion':'v1','kind':'Service','metadata':{'name':SERVICE,'namespace':NS},'spec':{'selector':{'app':SERVICE},'ports':[{'port':8080,'targetPort':8080}],'type':'ClusterIP'}}
    print(kube('apply','-f','-',input=json.dumps({'apiVersion':'v1','kind':'List','items':[doc,service]})))
    print(kube('rollout','status','deployment/'+SERVICE,'--timeout=180s'))
    pods=json.loads(kube('get','pods','-l','app='+SERVICE,'-o','json'))['items']
    pod=next(x for x in pods if not x['metadata'].get('deletionTimestamp')
             and x['spec']['containers'][0]['image']==v['image']
             and x['metadata'].get('annotations',{}).get('workshop/source-commit')==v['commit']
             and x.get('status',{}).get('containerStatuses')
             and all(s.get('ready') for s in x['status']['containerStatuses']))
    result={'pod':pod['metadata']['name'],'image':pod['spec']['containers'][0]['image'],'imageID':pod['status']['containerStatuses'][0]['imageID'],'expected':v};save('eks',result);print(json.dumps(result,indent=2))
def verify():
    c=config();v=load('image');e=load('ecs');k=load('eks');os.environ['KUBECONFIG']=str(A.absolute()/'kubeconfig')
    with urllib.request.urlopen('http://'+e['privateIp']+':8080/api/info',timeout=20) as r:ec=json.load(r)
    ek=json.loads(kube('exec',k['pod'],'--','python','-c',"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/api/info').read().decode())"))
    assert ec['commit']==ek['commit']==v['commit'], 'Source commit mismatch'
    assert ec['platform']=='ECS' and ek['platform']=='EKS'
    assert e['imageDigest']==v['digest'] and k['imageID'].endswith(v['digest']), 'Image digest mismatch'
    result={'status':'PASS','commit':v['commit'],'digest':v['digest'],'ecs':ec,'eks':ek};save('verification',result);print(json.dumps(result,indent=2))
if __name__=='__main__': {'build':build,'ecs':ecs,'eks':eks,'verify':verify}[sys.argv[1]]()
