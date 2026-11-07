import jenkins.model.Jenkins
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import jenkins.security.ApiTokenProperty
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec

def j=Jenkins.get()
def realm=new HudsonPrivateSecurityRealm(false)
def password=new File('/run/bootstrap/admin-password').text.trim()
def u=realm.createAccount('student',password)
j.setSecurityRealm(realm)
def auth=new FullControlOnceLoggedInAuthorizationStrategy();auth.setAllowAnonymousRead(false);j.setAuthorizationStrategy(auth)
j.setNumExecutors(1);j.setSlaveAgentPort(-1)
def home=new File(j.rootDir,'secrets/workshop-api-token')
if(!home.exists()) {home.text=u.getProperty(ApiTokenProperty.class).tokenStore.generateNewToken('workshop-cli').plainValue;u.save()}
def creds=SystemCredentialsProvider.getInstance().getCredentials()
if(!creds.find{it.id=='github-readonly'}) {
 creds.add(new BasicSSHUserPrivateKey(CredentialsScope.GLOBAL,'github-readonly','git',new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(new File('/run/bootstrap/github-readonly').text),'','Read-only key for this workshop repository'))
 SystemCredentialsProvider.getInstance().save()
}
if(j.getItem('container-delivery')==null) {
 def job=j.createProject(WorkflowJob,'container-delivery')
 def scm=new GitSCM([new UserRemoteConfig(System.getenv('WORKSHOP_REPO'),null,null,'github-readonly')],[new BranchSpec('*/main')],false,[],null,null,[])
 job.setDefinition(new CpsScmFlowDefinition(scm,'Jenkinsfile'));job.save()
}
j.save()
