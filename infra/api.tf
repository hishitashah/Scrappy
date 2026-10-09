# The API's AWS resources. This branch creates only the database secret; the Lambda, its
# Function URL, the log group and the IAM role join it in m4/infra-api (spec 10.7).

# Neon's pooled connection string, for the Lambda.
#
# Terraform creates the parameter with a placeholder and then ignores its value forever.
# The real secret is written once, by hand:
#
#   aws ssm put-parameter --name /scrappy/prod/database_url --type SecureString \
#     --value 'postgresql+psycopg://...' --overwrite
#
# That keeps it out of Terraform state, out of plan output, and out of git. SSM Parameter
# Store's standard tier is free; Secrets Manager would charge $0.40 a month per secret and
# is on the prohibited list in spec section 14.
resource "aws_ssm_parameter" "database_url" {
  name        = "/scrappy/prod/database_url"
  description = "Neon pooled connection string for the Scrappy API"
  type        = "SecureString"
  value       = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}
