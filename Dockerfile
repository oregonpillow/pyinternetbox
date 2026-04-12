FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml requirements.txt README.md ./
COPY internetbox_client/ internetbox_client/

RUN uv pip install --system .

EXPOSE 9101

CMD ["ibox", "export"]
