# Lets GitHub Actions deploy into this account without storing an AWS key anywhere
# (spec 10.7). GitHub presents a short-lived OIDC token per workflow run; AWS trades it for
# credentials that expire in minutes.

# AWS has validated GitHub's certificate against its own trust store since July 2023, so no
# thumbprint is pinned here — one less thing to rotate when GitHub changes certificates.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = []
}

data "aws_iam_policy_document" "github_deploy_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # The security model in one line: only a workflow running on main, in this repository,
    # can assume this role. A pull request — including one from a fork — gets nothing.
    #
    # The repository name is case-sensitive here. It is "Scrappy", not "scrappy": IAM
    # compares the claim literally, and the wrong case fails as an opaque AccessDenied.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:hishitashah/Scrappy:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "scrappy-github-deploy"
  description        = "Assumed by GitHub Actions on pushes to main"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume_role.json
}

# Broad permissions, narrow trust: the role can do anything, but almost nothing can assume
# it. Least privilege here is post-MVP item 5 — a deliberate shortcut, not an oversight.
resource "aws_iam_role_policy_attachment" "github_deploy_admin" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
