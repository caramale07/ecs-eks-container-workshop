#!/bin/bash
set -euo pipefail
umask 077
REPO=${1:?Git SSH URL required}
STACK=${2:-csci-ecs-eks-cicd}
REGION=${AWS_DEFAULT_REGION:-us-east-1}
cd /opt/csci-cicd
for i in {1..90}; do docker info >/dev/null 2>&1 && break; sleep 5; done
mkdir -p bootstrap
[ -f bootstrap/admin-password ] || openssl rand -hex 24 > bootstrap/admin-password
[ -f bootstrap/github-readonly ] || ssh-keygen -q -t ed25519 -N '' -f bootstrap/github-readonly -C csci-jenkins-readonly
cat > bootstrap/known_hosts <<'KEY'
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
KEY
chown -R 1000:1000 bootstrap
chmod 700 bootstrap
chmod 600 bootstrap/admin-password bootstrap/github-readonly
chmod 644 bootstrap/known_hosts bootstrap/github-readonly.pub
cp jenkins-init.groovy bootstrap/init.groovy
chown 1000:1000 bootstrap/init.groovy
chmod 644 bootstrap/init.groovy
docker build -t csci-jenkins:lab -f Jenkins.Dockerfile . > /var/log/csci-jenkins-image.log 2>&1
docker volume create csci-jenkins-home >/dev/null
DOCKER_GROUP=$(stat -c '%g' /var/run/docker.sock)
docker inspect csci-jenkins >/dev/null 2>&1 || docker run -d --name csci-jenkins --restart unless-stopped --network host --group-add "$DOCKER_GROUP" --memory 5g -e JAVA_OPTS='-Djenkins.install.runSetupWizard=false' -e JENKINS_OPTS='--httpListenAddress=127.0.0.1 --httpPort=8080' -e WORKSHOP_REPO="$REPO" -e AWS_DEFAULT_REGION="$REGION" -e LAB_STACK="$STACK" -v csci-jenkins-home:/var/jenkins_home -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD/bootstrap:/run/bootstrap:ro" -v "$PWD/bootstrap/init.groovy:/var/jenkins_home/init.groovy.d/workshop.groovy:ro" -v "$PWD/bootstrap/known_hosts:/var/jenkins_home/.ssh/known_hosts:ro" csci-jenkins:lab
for i in {1..120}; do
 if docker exec -u 0 csci-jenkins test -s /var/jenkins_home/secrets/workshop-api-token; then break; fi
 sleep 5
done
docker exec -u 0 csci-jenkins cat /var/jenkins_home/secrets/workshop-api-token > bootstrap/api-token
python3 - <<'PY'
import json,pathlib
p=pathlib.Path('bootstrap')
(p/'credentials.json').write_text(json.dumps({'username':'student','password':(p/'admin-password').read_text().strip(),'api_token':(p/'api-token').read_text().strip()}))
PY
aws secretsmanager create-secret --region "$REGION" --name csci-jenkins-workshop --secret-string file://bootstrap/credentials.json >/dev/null 2>&1 || aws secretsmanager put-secret-value --region "$REGION" --secret-id csci-jenkins-workshop --secret-string file://bootstrap/credentials.json >/dev/null
printf 'Jenkins public read-only deploy key\n'
cat bootstrap/github-readonly.pub
printf '\nJenkins service\n'
curl -s -o /dev/null -w 'Login page HTTP %{http_code}\n' http://127.0.0.1:8080/login
printf 'JENKINS_SETUP_COMPLETE\n'
