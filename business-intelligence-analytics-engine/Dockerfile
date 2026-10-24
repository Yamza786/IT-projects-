FROM rocker/r-ver:4.4.2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsqlite3-dev && rm -rf /var/lib/apt/lists/*
RUN Rscript -e 'install.packages(c("DBI", "RSQLite"), repos="https://cloud.r-project.org")'
COPY R R
COPY sql sql
COPY scripts scripts
COPY fixtures fixtures
RUN useradd --system --uid 10001 --create-home analyst && mkdir -p /data && chown analyst:analyst /data
USER 10001:10001
ENV BI_DATABASE=/data/analytics.sqlite
CMD ["Rscript", "scripts/bi.R", "report"]
