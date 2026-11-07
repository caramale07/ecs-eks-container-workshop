#!/usr/bin/env python3
"""Button-driven VS Code tasks. Students need not type deployment commands."""
import base64,io,json,os,pathlib,re,shlex,subprocess,sys,tarfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1];PRIVATE=ROOT/'.lab';PRIVATE.mkdir(exist_ok=True);os.chmod(PRIVATE,0o700)
os.environ.setdefault('AWS_DEFAULT_REGION','us-east-1');os.environ['AWS_PAGER']=''
os.environ['PATH']=str(PRIVATE/'bin')+os.pathsep+os.environ['PATH']
if (PRIVATE/'credentials').exists():os.environ['AWS_SHARED_CREDENTIALS_FILE']=str(PRIVATE/'credentials')
STACK='csci-ecs-eks-cicd'
def aws(*a):
 s=subprocess.check_output(['aws',*a,'--output','json'],text=True).strip();return json.loads(s) if s else None
def outputs():return {x['OutputKey']:x['OutputValue'] for x in aws('cloudformation','describe-stacks','--stack-name',STACK)['Stacks'][0]['Outputs']}
def remote(command):
 cid=aws('ssm','send-command','--instance-ids',outputs()['JenkinsId'],'--document-name','AWS-RunShellScript','--parameters',json.dumps({'commands':[command],'executionTimeout':['3600']}))['Command']['CommandId'];print('AWS Systems Manager command:',cid,flush=True)
 previous=None
 for _ in range(720):
  time.sleep(5)
  r=aws('ssm','get-command-invocation','--command-id',cid,'--instance-id',outputs()['JenkinsId'])
  if r['Status']!=previous:print('Status:',r['Status'],flush=True);previous=r['Status']
  if r['Status'] in ('Pending','InProgress','Delayed'):continue
  print(r['StandardOutputContent']);print(r['StandardErrorContent'])
  if r['Status']!='Success':raise SystemExit('Inspect this command in AWS Console Run Command before retrying.')
  return r['StandardOutputContent']
 raise SystemExit('Setup is still running. Inspect the command in AWS Console.')
mode=sys.argv[1]
if mode=='namespace':
 os.environ['KUBECONFIG']=str(PRIVATE/'kubeconfig')
 subprocess.run(['aws','eks','update-kubeconfig','--name',outputs()['EksCluster'],'--kubeconfig',os.environ['KUBECONFIG']],check=True)
 ns={'apiVersion':'v1','kind':'Namespace','metadata':{'name':'workshop'}}
 subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(ns),text=True,check=True)
 print('Workshop namespace is ready. Jenkins has edit access only in this namespace.')
elif mode=='jenkins':
 repo=sys.argv[2]
 if repo.startswith('https://github.com/'):repo='git@github.com:'+repo.split('https://github.com/')[1].removesuffix('.git')+'.git'
 if not re.fullmatch(r'git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git',repo):raise SystemExit('Use your GitHub repository HTTPS or SSH URL.')
 data=io.BytesIO()
 with tarfile.open(fileobj=data,mode='w:gz') as t:
  for name in ['Jenkins.Dockerfile','jenkins-init.groovy','setup_jenkins.sh']:t.add(ROOT/'infra'/name,arcname=name)
 command='set -e\nmkdir -p /opt/csci-cicd\ncd /opt/csci-cicd\nprintf %s '+shlex.quote(base64.b64encode(data.getvalue()).decode())+' | base64 -d | tar -xz\nbash setup_jenkins.sh '+shlex.quote(repo)+' '+STACK
 text=remote(command);key=re.search(r'ssh-ed25519 [A-Za-z0-9+/=]+ csci-jenkins-readonly',text)
 if key:(PRIVATE/'github-readonly.pub').write_text(key[0]+'\n');print('Open .lab/github-readonly.pub in VS Code. Add it in your GitHub repository Settings > Deploy keys. Keep Allow write access OFF.')
 print('Retrieve your Jenkins login in AWS Console > Secrets Manager > csci-jenkins-workshop. Do not submit or capture its value.')
elif mode=='previews':
 command='set -e\ncat > /opt/csci-cicd/start_previews.sh <<\'CSCI_PREVIEWS\'\n'+(ROOT/'infra/start_previews.sh').read_text()+'\nCSCI_PREVIEWS\nbash /opt/csci-cicd/start_previews.sh'
 remote(command)
elif mode=='tunnel':
 names={'jenkins':('8080','18080'),'ecs':('18081','18081'),'eks':('18082','18082')};remote_port,local_port=names[sys.argv[2]]
 print('Keep this task running. Open http://127.0.0.1:'+local_port,flush=True)
 subprocess.run(['aws','ssm','start-session','--target',outputs()['JenkinsId'],'--document-name','AWS-StartPortForwardingSession','--parameters',json.dumps({'portNumber':[remote_port],'localPortNumber':[local_port]})],check=True)
else:raise SystemExit('Unknown task')
