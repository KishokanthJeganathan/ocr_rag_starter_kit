# infra/

- `postgres/init.sql` — creates the `vector` extension and the RLS-enforced
  `ocr_app` application role. Mounted into the Postgres container at first boot;
  executed explicitly in CI.
- Terraform for AWS (ECS Fargate, RDS, S3, ElastiCache, ALB) lands in **Stage 11**.
