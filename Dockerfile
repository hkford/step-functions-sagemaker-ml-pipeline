FROM public.ecr.aws/lambda/python:3.8

# Necessary for VSCode Remote Containers
RUN yum update -y && yum install -y tar gzip
COPY ./ ./

RUN python3.8 -m pip install -r functions/preprocessing/requirements.txt
RUN python3.8 -m pip install pytest moto autopep8