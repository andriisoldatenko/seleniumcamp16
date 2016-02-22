#!/usr/bin/env bash

eval "$(docker-machine env sc16)"
docker run -p 8080:8080 -p 50000:50000 -v /Users/andrii/jenkins:/var/jenkins_home sc16-jenkins
