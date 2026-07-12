FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
RUN wget -q -O terraform.zip https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip && \
    unzip terraform.zip -d /usr/local/bin/ && \
    rm terraform.zip && \
    terraform --version

# Install Infracost CLI v2.8.0
RUN curl -fsSL https://raw.githubusercontent.com/infracost/cli/master/scripts/install.sh | sh && \
    infracost --version

COPY backend/requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=300
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY backend/ .
COPY terraform/ /app/terraform/
COPY scripts/ /app/scripts/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "run.py"]
