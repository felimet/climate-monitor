FROM apache/superset:latest

USER root

# Install CrateDB driver and its dependencies
RUN uv pip install crate sqlalchemy-cratedb==0.40.1

USER superset
