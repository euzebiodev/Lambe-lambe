pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare') {
            steps {
                sh '''
                    python3 -m venv .venv-ci
                    . .venv-ci/bin/activate
                    python -m pip install --upgrade pip wheel
                    python -m pip install -r requirements-service.txt pytest pytest-cov
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . .venv-ci/bin/activate
                    pytest
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh 'sudo /opt/album-polaroid/deploy-album-polaroid.sh "$WORKSPACE"'
            }
        }

        stage('Health') {
            steps {
                sh '''
                    PASSWORD="$(sudo sed -n 's/^POLAROID_PASSWORD=//p' /etc/album-polaroid/album-polaroid.env)"
                    curl -fsS -u "admin:$PASSWORD" http://127.0.0.1:8091/ >/dev/null
                '''
            }
        }
    }
}
