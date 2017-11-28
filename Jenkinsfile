#!/usr/bin/env groovy
import hudson.plugins.cobertura.targets.CoverageMetric;

pipeline {
  agent any
  stages {
    stage('Setup') {
      steps {
        sh 'eval "$(pyenv init -)"'
        sh 'pyenv install -s pypy-5.0.1'
        sh 'pyenv install -s 2.6.8'
        sh 'pyenv install -s 2.7.10'
        sh 'pyenv local 2.6.8 2.7.10 pypy-5.0.1'
      }
    }
    stage('Unit test') {
      steps {
        sh 'tox -e py26,py27,pypy --recreate -- --junitxml=results/\'$TOXENV\'-results.xml'
      }
    }
    stage('Linter') {
      steps {
        sh 'tox --recreate -e flake8'
      }
    }
    stage('Coverage') {
      steps {
        sh 'tox -e py27 --recreate -- --cov=abusehelper --cov-report term-missing --cov-report xml:results/cov.xml'
      }
    }
  }
  post {
    success {
      script {
        percentage = manager.build.getAction(hudson.plugins.cobertura.CoberturaBuildAction.class).getResults()[CoverageMetric.LINE].getPercentageFloat();
        if (percentage > 80) {
            bgcolour = "greenyellow";
        }
        else if (percentage > 50) {
            bgcolour = "yellow";
        }
        else {
            bgcolour = "red";
        }
        textpercentage = "Coverage: " + Math.round(percentage).toString() + "%";
        manager.addShortText(textpercentage, "black", bgcolour, "2px", "black");
      }
    }
    failure {
      emailext body: '${BUILD_URL}', recipientProviders: [[$class: 'DevelopersRecipientProvider']], replyTo: 'vuolteen@abusesa.com', subject: 'FAILURE: ${JOB_NAME} ${BUILD_DISPLAY_NAME}', to: 'vuolteen@abusesa.com'
    }
    always {
      sh 'pyenv local --unset'
      archiveArtifacts artifacts: 'results/*'
      junit '**/results/*.xml'
      step([$class: 'CoberturaPublisher', autoUpdateHealth: false, autoUpdateStability: false, coberturaReportFile: '**/results/cov.xml', failNoReports: false, failUnhealthy: false, failUnstable: false, maxNumberOfBuilds: 0, onlyStable: false, sourceEncoding: 'ASCII', zoomCoverageChart: false])
      deleteDir()
    }
  }
}
