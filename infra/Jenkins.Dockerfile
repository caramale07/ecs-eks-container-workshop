FROM jenkins/jenkins:lts-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends docker.io docker-cli python3 curl unzip jq && rm -rf /var/lib/apt/lists/*
RUN curl -fsS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/aws.zip && unzip -q /tmp/aws.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/aws.zip
ARG KUBECTL_VERSION=v1.35.0
RUN curl -fsSLO https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl && curl -fsSLO https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl.sha256 && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && install -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl kubectl.sha256
USER jenkins
RUN jenkins-plugin-cli --plugins workflow-aggregator git github ssh-credentials
