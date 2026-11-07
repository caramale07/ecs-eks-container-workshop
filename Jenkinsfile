pipeline {
  agent any
  options { disableConcurrentBuilds(); timeout(time: 35, unit: 'MINUTES'); buildDiscarder(logRotator(numToKeepStr: '10')) }
  parameters { booleanParam(name: 'CLOUD_EXTENSION', defaultValue: false, description: 'Run controlled failure, rollback and scaling comparison in this disposable lab') }
  triggers { pollSCM('* * * * *') }
  environment { AWS_DEFAULT_REGION = 'us-east-1'; LAB_STACK = 'csci-ecs-eks-cicd'; AWS_PAGER = '' }
  stages {
    stage('Test') { steps { sh 'rm -f artifacts/*.json'; sh 'python3 -m unittest discover -s tests -v' } }
    stage('Build and push immutable image') { steps { sh 'python3 scripts/lab.py build' } }
    stage('Deploy ECS production') { steps { sh 'python3 scripts/lab.py ecs' } }
    stage('Deploy EKS production') { steps { sh 'python3 scripts/lab.py eks' } }
    stage('Verify source and digest') { steps { sh 'python3 scripts/lab.py verify' } }
    stage('Cloud Computing recovery extension') { when { expression { params.CLOUD_EXTENSION } }; steps { sh 'python3 scripts/cloud_extension.py' } }
  }
  post { always { archiveArtifacts artifacts: 'artifacts/*.json', allowEmptyArchive: true } }
}
